import io
import logging

import geopandas as gpd
import ipywidgets as widgets
import matplotlib as mpl
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from ipywidgets import FloatRangeSlider, Layout, Output, VBox, jsdlink
from lonboard import Map, PolygonLayer
from lonboard.basemap import CartoStyle
from lonboard.controls import MultiRangeSlider
from lonboard.layer_extension import DataFilterExtension
from shapely.geometry import Point

from src.utils.loaders import process_loaded_building_df
from src.utils.vis.colors_utils import CategoricalColorMap

logger = logging.getLogger(__name__)


class MapWrapper:

    def __init__(
        self,
        b_gdf: gpd.GeoDataFrame,  # crs should be 4326
        bp_gdf: gpd.GeoDataFrame,  # crs should be 4326
        colored_landuse_gdf: gpd.GeoDataFrame = None,  # can be any crs
        default_height_cmap: str = "viridis",
        no_parts: bool = False,
    ):
        self.height_values = (b_gdf["height_calc"], bp_gdf["height_calc"])
        # both buildings and building_parts
        self.height_vmin = np.min(
            [np.min(self.height_values[0]), np.min(self.height_values[1])]
        )
        self.height_vmax = np.max(
            [np.max(self.height_values[0]), np.max(self.height_values[1])]
        )

        print(self.height_values[0].head())

        # choropleth colors
        cmap = plt.get_cmap(default_height_cmap)
        norm = mpl.colors.Normalize(vmin=self.height_vmin, vmax=self.height_vmax)

        self.b_layer = PolygonLayer.from_geopandas(
            b_gdf,
            extruded=True,
            get_elevation=b_gdf["height_calc"],
            get_fill_color=(cmap(norm(self.height_values[0])) * 255).astype(np.uint8),
        )

        self.bp_layer = PolygonLayer.from_geopandas(
            bp_gdf,
            extruded=True,
            get_elevation=bp_gdf["height_calc"],
            get_fill_color=(cmap(norm(self.height_values[1])) * 255).astype(np.uint8),
        )

        self.show_landuse = colored_landuse_gdf is not None
        if self.show_landuse:
            colored_landuse_gdf = colored_landuse_gdf.copy().to_crs(4326)

            # ASSUMED IN HEX
            # this is so annoying
            landuse_color_hex = colored_landuse_gdf["color"]

            landuse_color_rgb = np.array(
                [[int(h[i : i + 2], 16) for i in (1, 3, 5)] for h in landuse_color_hex]
            )

            landuse_color_rgba = np.column_stack(
                [landuse_color_rgb, np.full(len(landuse_color_rgb), 255)]
            )
            self.landuse_layer = PolygonLayer.from_geopandas(
                colored_landuse_gdf,
                get_fill_color=landuse_color_rgba.astype(np.uint8),
            )
        self._m = Map(
            layers=[self.b_layer]
            + ([self.bp_layer] if not no_parts else [])
            + ([self.landuse_layer] if self.show_landuse else []),
            # basemap=CartoStyle.PositronNoLabels,
            layout=Layout(flex="1"),
            height=720,
        )

        self._m.set_view_state(
            longitude=103.8557931,
            latitude=1.2843934,
            pitch=70,
            bearing=340,
            zoom=14,
        )

    @property
    def m(self):
        return self._m

    def set_fill_color_getters(self, b_getter, bp_getter):
        self.b_layer.get_fill_color = b_getter(self.b_layer)
        self.bp_layer.get_fill_color = bp_getter(self.bp_layer)


class MapExplorer:

    def __init__(
        self,
        building_gdf: gpd.GeoDataFrame,
        building_part_gdf: gpd.GeoDataFrame = None,
        default_building_height: float = 6,
        default_floor_height: float = 4,
        default_cmap: str = "viridis",
        enable_debug_mode: bool = False,  # shows only a small subset of the buildings
    ):
        """
        Input CRS doesn't matter, a copy will be reprojected to 4326 for visualization

        Expected input columns:
        * `id`, `names`, `sources`
        * `height`, `min_height`
        * `is_underground`, `num_floors`, `num_floors_underground`, `min_floor`
        * `subtype`, `class`, `has_parts` - only for building
        * `geometry`
        * `building_id` - only available if it's building_part
        * Removed: `level`, `roof_*`, `facade-*`, `version`, `type` (just building, building_part)
        """

        # very jank approach to supporting not rendering bpart
        # because in my infinite wisdom I did not expect to not need to render that, and now
        # it's a problem
        if building_part_gdf is None:
            # copy the smallest building in b_gdf
            building_part_gdf = building_gdf.sort_values(by="area_m2").head(2).copy()
            # add columns that need to exist downstream
            building_part_gdf["building_id"] = pd.Series(dtype="str")

        # copy - because I might make changes for visualization purposes
        # lonboard can only use EPSG-4326
        self.b_gdf = building_gdf.copy().to_crs(4326)
        self.bp_gdf = building_part_gdf.copy().to_crs(4326)

        # geometry series that remains in EPSG-3414, with indices for conversion
        self._b_geometry_metric: gpd.GeoSeries
        self._b_geometry_metric = building_gdf["geometry"]
        self._bp_geometry_metric: gpd.GeoSeries
        self._bp_geometry_metric = building_gdf["geometry"]

        self.defaults = {
            "building_height": default_building_height,
            "floor_height": default_floor_height,
            "default_cmap": default_cmap,
        }

        # debug mode building selection - set distance threshold around a point in downtown
        if enable_debug_mode:
            # make sure point is in correct crs
            reference_point = (
                gpd.GeoSeries([Point(103.852386, 1.292699)], crs=4326)
                .to_crs(3414)
                .iloc[0]
            )
            distance_threshold = 5 * 1000

            # use spatial join
            self.b_gdf = self.b_gdf[
                self._b_geometry_metric.intersects(
                    reference_point.buffer(distance_threshold)
                )
            ]

            self.bp_gdf = self.bp_gdf[self.bp_gdf["building_id"].isin(self.b_gdf.index)]

        self.bp_gdf = (
            self.bp_gdf.drop(columns=["area_m2"]).merge(
                self.b_gdf[["subtype", "class", "area_m2"]],  # no id
                left_on="building_id",
                # right_on="id",
                right_index=True,
                how="left",
                validate="m:1",
            )
            # .drop(columns=["id_y"])
            # .rename(columns={"id_x": "id"})
        )

        def process_input_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
            """Processes input building and building_part gdfs for internal use.

            * Calculates estimated heights for buildings that
            don't have height, stores in `height_calc`. Simple calculation: 3.5m * floors if available,
            else default height of 6m.
            * Removes gdf columns of type `geometry` apart from the main `geometry` column,
            as lonboard doesn't like it when there is more than one geometry column.

            Args:
                gdf (gpd.GeoDataFrame): input gdf

            Returns:
                gpd.GeoDataFrame: modified gdf
            """
            # process visual floor heights
            # TODO improve
            gdf["height_calc"] = np.select(
                condlist=[
                    ~gdf["height"].isna(),
                    gdf["height"].isna() & ~gdf["num_floors"].isna(),
                ],
                choicelist=[gdf["height"], gdf["num_floors"] * 3.5],
                default=6,
            )

            # remove geometry-type columns apart from the main "geometry" col
            # e.g. calculated centroid
            cols = [
                col
                for col in gdf.select_dtypes(include=["geometry"]).columns
                if col != "geometry"
            ]
            gdf = gdf.drop(columns=cols)

            return gdf

        self.b_gdf = process_input_gdf(self.b_gdf)
        self.bp_gdf = process_input_gdf(self.bp_gdf)

    # ==== properties ====
    @property
    def b_gdf_metric(self) -> gpd.GeoDataFrame:  # in metric CRS
        return self.b_gdf.drop(columns=["geometry"]).join(
            self._b_geometry_metric, how="left"
        )  # join on index

    @property
    def bp_gdf_metric(self) -> gpd.GeoDataFrame:  # in metric CRS
        return self.bp_gdf.drop(columns=["geometry"]).join(
            self._bp_geometry_metric, how="left"
        )  # join on index

    # ==== widgets ====

    def make_categorical_legend_widget(
        self,
        categorical_color_mapping: CategoricalColorMap,
        group_non_distinct: bool = True,
    ) -> widgets.VBox:
        """Makes a categorical (discrete colors) legend widget based on a supplied (label, color) mapping.

        Args:
            categorical_color_mapping (CategoricalColorMap): _description_.
            group_non_distinct (bool, optional): _description_. Defaults to True.

        Returns:
            widgets.VBox: _description_
        """

        legend_items = []

        if not group_non_distinct:
            label_color_mappings = categorical_color_mapping.mapping.items()
        else:
            label_color_mappings = (
                categorical_color_mapping.mapping_others_grouped.items()
            )

        for category, color in label_color_mappings:
            swatch = widgets.HTML(value=f"""
                <div style="
                    width:16px;
                    height:16px;
                    background:{mcolors.to_hex(color)};
                    margin-right:6px;
                    display:inline-block;
                    vertical-align:middle;
                "></div>
                """)
            label = widgets.HTML(value=f"<span>{category}</span>")

            legend_items.append(
                widgets.HBox(
                    [swatch, label], layout=widgets.Layout(align_items="center")
                )
            )

        legend = widgets.VBox(
            legend_items,
            layout=widgets.Layout(
                padding="6px",
                # border="1px solid #ccc",
                # background="white",
                width="240px",
            ),
        )
        return legend

    def make_histogram_vertical_widget(
        self, data_series: pd.Series, title: str = "histogram", **kwargs
    ):
        # use kwargs to directly pass pyplot.hist formatting
        fig = plt.figure(figsize=(4, 16), dpi=40)

        # set some custom default params:
        if "bins" not in kwargs:
            kwargs["bins"] = 30

        plt.hist(data_series, orientation="horizontal", **kwargs)

        plt.title(title)

        # Render figure into memory
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)

        # Put it into an ipywidget
        img = widgets.Image(
            value=buf.getvalue(),
            format="png",
            width=240,
        )

        num_nan = data_series.isna().sum()
        num_non_nan = len(data_series) - num_nan

        return widgets.VBox(
            [
                img,
                widgets.Label(f"{num_non_nan} non-NaN values"),
                widgets.Label(f"{num_nan} NaN values"),
            ]
        )

    def make_title_widget(self, title: str):
        return widgets.HTML(f"""
            <div style="
                font-size: 20px;
                font-weight: 600;
                padding: 8px 0;
                border-bottom: 1px solid #ddd;
            ">
                {title}
            </div>
            """)

    # ===== final output builds ======

    def build_basic(self):
        # just a basic map
        map_wrapper = MapWrapper(self.b_gdf, self.bp_gdf, default_height_cmap="viridis")
        m = map_wrapper.m

        return widgets.VBox([m])

    def build_singleprop(
        self,
        column: str = "",
        categorical_cmap: CategoricalColorMap = None,
        continuous_cmap_name: str = "viridis",
        colored_landuse_gdf: gpd.GeoDataFrame = None,  # has to have color column
        title: str = "",
    ):
        """build map based on just one property"""

        try:
            out = widgets.Output()

            # @out.capture(clear_output=False)

            b_values = self.b_gdf[column]
            bp_values = self.bp_gdf[column]

            map_wrapper = MapWrapper(
                self.b_gdf,
                self.bp_gdf,
                colored_landuse_gdf,
                default_height_cmap=continuous_cmap_name,
            )
            m = map_wrapper.m

            b_layer, bp_layer = map_wrapper.b_layer, map_wrapper.bp_layer
            right_bar = widgets.VBox()  # initialize empty

            if pd.api.types.is_numeric_dtype(
                b_values
            ) and not pd.api.types.is_bool_dtype(b_values):
                combined_values = np.concat([b_values, bp_values])
                vmin = np.nanmin(combined_values)
                vmax = np.nanmax(combined_values)

                b_layer.get_fill_color, _ = apply_continuous_colormap(
                    b_values, vmin, vmax, cmap_name=continuous_cmap_name
                )
                bp_layer.get_fill_color, _ = apply_continuous_colormap(
                    bp_values, vmin, vmax, cmap_name=continuous_cmap_name
                )
                # no histogram for now
            elif categorical_cmap:
                b_layer.get_fill_color, _ = apply_categorical_colormap(
                    b_values, k=10, color_mapping=categorical_cmap
                )
                bp_layer.get_fill_color, _ = apply_categorical_colormap(
                    bp_values, k=10, color_mapping=categorical_cmap
                )
                right_bar.children = [
                    self.make_categorical_legend_widget(categorical_cmap)
                ]
            else:
                b_layer.get_fill_color, cat_cmap = apply_categorical_colormap(
                    b_values, k=10
                )
                bp_layer.get_fill_color, _ = apply_categorical_colormap(
                    bp_values, color_mapping=cat_cmap, k=10
                )
                right_bar.children = [self.make_categorical_legend_widget(cat_cmap)]

            app = widgets.VBox(
                (
                    ([self.make_title_widget(title)] if title else [])
                    + [
                        widgets.HBox([m, right_bar]),
                        out,
                    ]
                ),
                # layout=widgets.Layout(flex="1", padding="10px", overflow="auto"),
            )

        except Exception as e:
            logger.exception(e, exc_info=True)

        return app

    def build_configurable(
        self,
        viewable_columns: list[str] = [
            "height_calc",
            "subtype",
            "class",
            "num_floors",
            "area_m2",
        ],
        colored_landuse_gdf: gpd.GeoDataFrame = None,  # has to have color column
        height_cmap: str = "viridis",
        show_histogram: bool = True,
        title: str = "",
    ):
        try:
            # configurable - able to select which property to display

            out = widgets.Output()

            map_wrapper = MapWrapper(
                self.b_gdf,
                self.bp_gdf,
                colored_landuse_gdf,
                default_height_cmap=height_cmap,
            )
            m = map_wrapper.m

            height_vmin, height_vmax = map_wrapper.height_vmin, map_wrapper.height_vmax

            prop_selector_widget = widgets.Dropdown(
                options=viewable_columns,
                value=viewable_columns[0],
                description="property: ",
            )

            right_bar = widgets.VBox()  # initialize empty

            @out.capture(clear_output=False)
            def update_visualized_property(change):
                new_col = change["new"]
                b_layer, bp_layer = map_wrapper.b_layer, map_wrapper.bp_layer

                if new_col == "height_calc":
                    b_layer.get_fill_color, _ = apply_continuous_colormap(
                        self.b_gdf["height_calc"], height_vmin, height_vmax
                    )
                    bp_layer.get_fill_color, _ = apply_continuous_colormap(
                        self.bp_gdf["height_calc"], height_vmin, height_vmax
                    )
                    right_bar.children = []
                elif pd.api.types.is_numeric_dtype(
                    self.b_gdf[new_col]
                ) and not pd.api.types.is_bool_dtype(self.b_gdf[new_col]):
                    b_layer.get_fill_color, _ = apply_continuous_colormap(
                        self.b_gdf[new_col]
                    )
                    bp_layer.get_fill_color, _ = apply_continuous_colormap(
                        self.bp_gdf[new_col]
                    )
                    if show_histogram:
                        right_bar.children = [
                            self.make_histogram_vertical_widget(
                                self.b_gdf[new_col],
                                title=new_col,
                            )
                        ]
                else:
                    b_layer.get_fill_color, cat_cmap = apply_categorical_colormap(
                        self.b_gdf[new_col], k=10
                    )
                    bp_layer.get_fill_color, _ = apply_categorical_colormap(
                        self.bp_gdf[new_col], color_mapping=cat_cmap, k=10
                    )
                    right_bar.children = [self.make_categorical_legend_widget(cat_cmap)]

            # very jank, make it initialize the first visualization
            update_visualized_property({"new": viewable_columns[0]})

            prop_selector_widget.observe(update_visualized_property, names="value")

            # set up widgets for display
            # select based on options
            vertical_widgets = []
            if title:
                vertical_widgets.append(self.make_title_widget(title))

            vertical_widgets += [
                prop_selector_widget,
                widgets.HBox([m, right_bar]),
                out,  # text output
            ]

            app = widgets.VBox(
                vertical_widgets,
                # layout=widgets.Layout(flex="1", padding="10px", overflow="auto"),
            )

        except Exception as e:
            logger.exception(e, exc_info=True)

        return app

    def build_configurable_landuse(
        self,
        landuse_gdf: gpd.GeoDataFrame,
        viewable_columns: list[str] = [],
        title: str = "",
    ):
        """
        This is very much for testing, it's not actually that configurable
        """
        try:
            # configurable - able to select which property to display

            out = widgets.Output()

            layer = PolygonLayer.from_geopandas(
                landuse_gdf.copy().to_crs(4326),
                # get_fill_color=(cmap(norm(self.height_values[0])) * 255).astype(np.uint8),
            )

            m = Map(
                layers=layer,
                # basemap=CartoStyle.PositronNoLabels,
                layout=Layout(flex="1"),
                height=720,
            )

            m.set_view_state(
                longitude=103.8557931,
                latitude=1.2843934,
                pitch=70,
                bearing=340,
                zoom=14,
            )

            prop_selector_widget = widgets.Dropdown(
                options=viewable_columns,
                value=viewable_columns[0],
                description="property: ",
            )

            right_bar = widgets.VBox()  # initialize empty

            @out.capture(clear_output=False)
            def update_visualized_property(change):
                new_col = change["new"]

                if pd.api.types.is_numeric_dtype(
                    landuse_gdf[new_col]
                ) and not pd.api.types.is_bool_dtype(landuse_gdf[new_col]):
                    layer.get_fill_color, _ = apply_continuous_colormap(
                        landuse_gdf[new_col]
                    )
                    right_bar.children = []
                else:
                    layer.get_fill_color, cat_cmap = apply_categorical_colormap(
                        landuse_gdf[new_col], k=10
                    )
                    right_bar.children = [self.make_categorical_legend_widget(cat_cmap)]

            prop_selector_widget.observe(update_visualized_property, names="value")

            # very jank, make it initialize the first visualization
            update_visualized_property({"new": viewable_columns[0]})

            # set up widgets for display
            # select based on options
            vertical_widgets = []
            if title:
                vertical_widgets.append(self.make_title_widget(title))

            vertical_widgets += [
                prop_selector_widget,
                widgets.HBox([m, right_bar]),
                out,  # text output
            ]

            app = widgets.VBox(
                vertical_widgets,
                # layout=widgets.Layout(flex="1", padding="10px", overflow="auto"),
            )

        except Exception as e:
            logger.exception(e, exc_info=True)

        return app

    # ======== Utils ==========


def apply_continuous_colormap(
    data_series: pd.Series,
    vmin: float = None,
    vmax: float = None,
    show_nan: bool = True,
    cmap_name: str = "viridis",
):
    # colors
    nan_color = mcolors.to_rgba(mcolors.CSS4_COLORS["lightgray"])
    cmap = plt.get_cmap(cmap_name)

    assert pd.api.types.is_numeric_dtype(
        data_series
    ), "Data series for continuous colormap must be numeric."

    if show_nan:
        cmap.set_bad(nan_color)

    if not vmin:
        vmin = np.min(data_series)
    if not vmax:
        vmax = np.max(data_series)

    norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
    values_colors = (cmap(norm(data_series)) * 255).astype(np.uint8)
    return values_colors, None  # TODO should return some kind of legend


def apply_categorical_colormap(
    data_series: pd.Series,
    k: int = 5,
    show_nan: bool = True,
    nan_color=mcolors.CSS4_COLORS["lightgrey"],
    color_mapping: CategoricalColorMap = None,  # supplied categorical colormap to be applied directly
):
    """Applies a colormap to a categorical data series.
    Color map is either generateed based on the data, or a supplied color mapping.

    Args:
        data_series (pd.Series): _description_
        k (int, optional): _description_. Defaults to 5.
        show_nan (bool, optional): _description_. Whether or not to separately show.
            What happens if NaN is not specified????
        nan_color (optional): Color for NaN values.
            Defaults to the matplotlib "lightgrey" with alpha=0.5.
            Passed directly to CategoricalColorMap without conversions.
        color_mapping (CategoricalColorMap): Supplied CategoricalColorMap mapping object for the data.

    Returns:
        (array of data values' colors in [0, 255], CategoricalColorMap object)
    """

    if not color_mapping:
        assert k >= 2
        assert k <= 20, "Maximum of 20 categories for a colormap."
        if k <= 10:
            cmap = plt.get_cmap("tab10")
        else:
            cmap = plt.get_cmap("tab20")

        # if show_nan:
        #     cmap.set_bad(nan_color)

        # find top k categories
        k -= 1  # named categories + other
        val_counts = data_series.value_counts()
        top_k = val_counts.nlargest(k)
        top_k_labels = top_k.index.to_list()
        others = val_counts.nsmallest(len(val_counts) - k)
        others_labels = others.index.to_list()

        top_k_colors = [cmap(i) for i in range(len(top_k_labels))]
        # print(colors)

        color_mapping = CategoricalColorMap(
            cat_colors=top_k_colors,
            cat_labels=top_k_labels,
            cat_counts=top_k.array,
            others_color=cmap(k),
            others_labels=others_labels,
            others_count=np.sum(others.array),
            nan_color=nan_color if show_nan else None,
            nan_count=data_series.isna().sum() if show_nan else 0,
        )

    values_colors = (
        np.array([color_mapping.mapping[val] for val in data_series.fillna("nan")])
        * 255
    ).astype(np.uint8)

    # TODO what happens when supplied color_mapping may not be the same as data values????

    return values_colors, color_mapping


# =======================================


def main():
    # run some tests
    print("testing")

    building_gdf = gpd.read_parquet(r"singapore_building-20260819.parquet")
    building_part_gdf = gpd.read_parquet(r"singapore_building_part-20260819.parquet")

    map_helper = MapExplorer(
        building_gdf=process_loaded_building_df(building_gdf),
        building_part_gdf=process_loaded_building_df(building_part_gdf),
    )

    map_helper.build_configurable_landuse()


if __name__ == "__main__":
    main()
