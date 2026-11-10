import matplotlib.colors as mcolors
import numpy as np

DEFAULT_MASTERPLAN_LANDUSE_COLORS = {
    "RESIDENTIAL": "#f4ba82",
    "RESIDENTIAL WITH COMMERCIAL AT 1ST STOREY": "#e88284",
    "COMMERCIAL & RESIDENTIAL": "#35ade5",
    "COMMERCIAL": "#1e5689",
    "HOTEL": "#8b79b0",
    "WHITE": "#f5f2f2",
    "BUSINESS PARK": "#007aa0",
    "BUSINESS PARK - WHITE": "#007aa0",
    "BUSINESS 1": "#d5adc7",
    "BUSINESS 2": "#9f0d5c",
    "BUSINESS 1 - WHITE": "#d5adc7",
    "BUSINESS 2 - WHITE": "#9f0d5c",
    "RESIDENTIAL / INSTITUTION": "#f09c35",
    "COMMERCIAL / INSTITUTION": "#9effff",
    "HEALTH & MEDICAL CARE": "#cc0021",
    "EDUCATIONAL INSTITUTION": "#f2f2c1",
    "PLACE OF WORSHIP": "#cc0021",
    "CIVIC & COMMUNITY INSTITUTION": "#d13d1f",
    "OPEN SPACE": "#99ad00",
    "PARK": "#009f34",
    "BEACH AREA": "#fff370",
    "SPORTS & RECREATION": "#a3d39b",
    "WATERBODY": "#bfddf4",
    "ROAD": "#021515",
    "TRANSPORT FACILITIES": "#646869",
    "MASS RAPID TRANSIT": "#646869",
    "LIGHT RAPID TRANSIT": "#646869",
    "UTILITY": "#646869",
    "CEMETERY": "#9e8900",
    "AGRICULTURE": "#8c875b",
    "PORT / AIRPORT": "#646869",
    "RESERVE SITE": "#e5e765",
    "SPECIAL USE": "#476902",
}


def get_color_by_name(name: str):
    """Returns colors as hex codes (from matplotlib.colors)

    Args:
        name (str): _description_

    Returns:
        _type_: _description_
    """
    name = name.lower()
    if name in mcolors.CSS4_COLORS:
        return mcolors.CSS4_COLORS[name]

    return mcolors.XKCD_COLORS["xkcd:" + name]


class CategoricalColorMap:
    # custom class to handle categorical color map info
    def __init__(
        self,
        cat_colors,
        cat_labels: list[str],
        cat_counts: float = 0,  # not currently used
        others_color=None,
        others_labels: list[str] = [],
        others_count: float = 0,  # not currently used
        nan_color=None,
        nan_count: float = 0,  # not currently used
    ):
        """
        All colors supplied should be a form readable by matplotlib.colors.to_rgba_array()

        This will convert all colors to RGBA arrays in [0, 1]
        """
        # helpers and defaults
        DEFAULT_NAN_COLOR = np.array([210, 210, 210, 140])
        DEFAULT_OTHERS_COLOR = np.array([170, 170, 170, 255])
        to_rgba = mcolors.to_rgba_array
        # to_8bit = lambda x: np.rint(x * 255).astype(np.uint8)

        self.cat_colors = to_rgba(cat_colors)
        self.cat_labels = cat_labels
        self.cat_counts = cat_counts

        self._show_others = others_color is not None or others_count
        self.others_color = (
            DEFAULT_OTHERS_COLOR
            if others_color is None
            else to_rgba(others_color).squeeze()
        )
        self.others_labels = others_labels
        self.others_count = others_count

        self._show_nan = nan_color is not None or nan_count
        self.nan_color = (
            DEFAULT_NAN_COLOR
            if nan_color is None
            else to_rgba(nan_color).squeeze()
        )
        self.nan_count = nan_count

    @property
    def mapping(self):
        zipped = list(zip(self.cat_labels, self.cat_colors))

        if self._show_others:
            for l in self.others_labels:
                zipped.append((l, self.others_color))
        if self._show_nan:
            zipped.append(("nan", self.nan_color))

        return dict(zipped)

    @property
    def mapping_others_grouped(self):
        zipped = list(zip(self.cat_labels, self.cat_colors))

        if self._show_others:
            zipped.append((self.others_string, self.others_color))
        if self._show_nan:
            zipped.append(("nan", self.nan_color))

        return dict(zipped)

    @property
    def mapping_others_grouped_short(self):
        zipped = list(zip(self.cat_labels, self.cat_colors))

        if self._show_others:
            zipped.append(("other", self.others_color))
        if self._show_nan:
            zipped.append(("nan", self.nan_color))

        return dict(zipped)

    # @property
    # def total_count(self):
    #     return np.sum(self.cat_counts) + self.others_count + self.nan_count

    # @property
    # def total_count_no_nan(self):
    #     return self.total_count - self.nan_count

    @property
    def others_string(self):
        return "others: " + ", ".join(self.others_labels)
