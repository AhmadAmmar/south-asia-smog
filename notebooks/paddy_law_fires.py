# %% [markdown]
# # Saving groundwater, burning later: a natural experiment in Punjab
#
# **Question.** Punjab (2008 ordinance, 2009 Act) and Haryana (2009) banned transplanting rice before mid-June, to save
# groundwater: rice planted with the monsoon needs less pumping. A later rice crop is harvested later, and the stubble
# burnt between rice harvest and wheat sowing moves later too, towards November, when cooler, calmer air traps smoke
# over the plains around Delhi. Did that happen, and can it be pinned on the law?
#
# **Design.** Pakistan's Punjab grows the same rice-wheat rotation in the same climate, seen by the same satellites, with
# no such law. Comparing the two before and after 2009 removes what both share (weather, satellite changes). This is a
# *difference in differences*; it only works if the two were moving in parallel before the law, which we check.
#
# **Data.** MODIS Terra and Aqua active fires (1 km, daily, 2003-2025, 15 Sep-15 Dec) counted inside each region in
# Earth Engine (`src/60_paddy_law_fires.py`); groundwater from GRACE (the south-asia-groundwater project). Figures and
# statistics: `src/61_paddy_law_figures.py`.

# %%
import pandas as pd
from pathlib import Path
from IPython.display import Image
R = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
t = pd.read_csv(R / "outputs/paddy_law_fire_timing.csv")
t.pivot(index="year", columns="region", values=["fires", "d50", "share_nov"]).round(2)

# %% [markdown]
# `d50` is the day of the year by which half the season's fire pixels had burnt (day 305 = 1 November);
# `share_nov` the share burnt from 1 November on.
#
# ## Groundwater, burning date and November share together

# %%
Image(R / "figures/paddy_law_groundwater_fires.png", width=900)

# %% [markdown]
# ## The burning season, before and after

# %%
Image(R / "figures/paddy_law_fire_curves.png", width=800)

# %% [markdown]
# ## The statistics
# A segmented regression of the median date on a linear trend plus a step from 2010, with errors that allow for
# correlation between neighbouring years (HAC). The key line is the last: the India-minus-Pakistan gap.

# %%
pd.read_csv(R / "outputs/paddy_law_stats.csv").round(2)

# %% [markdown]
# ## What it means
# - **Burning moved into November in India's Punjab and Haryana.** The median date went from about 24 October
#   (2003-2008) to about 3 November (2010-2025); the share of fires from November on went from about a quarter to
#   about 60 per cent. That is the season when smoke is trapped worst over Delhi and Lahore.
# - **The law cannot be cleanly credited.** The date was already moving later by about half a day a year before 2009
#   (advisories on later transplanting came earlier). India's own series steps about 3 days at the law, but against
#   Pakistan's Punjab the step is small and not significant, and the two regions were not moving in parallel before
#   2009 (the gap was already narrowing), which weakens the difference-in-differences.
# - **Groundwater kept falling.** GRACE shows Indian Punjab and Haryana losing storage throughout, faster than
#   Pakistan's Punjab; the law slowed the loss at best (see the south-asia-groundwater period trends: -4.4, -2.3,
#   -2.0 cm/yr in 2002-09, 2010-17, 2018-latest).
# - **A trade-off to name plainly:** a groundwater policy shifted air pollution into the worst weeks for smog.
#   Better residue management (in-field machines, ex-situ use) breaks the trade-off; fire counts fell sharply in 2025.
#
# **Caveats.** Satellite fire pixels miss small or brief fires and fires lit after the afternoon overpass (see
# `src/03_fire_timing.py`: farmers may now burn later in the day); MODIS counts are comparable across years because the
# same two sensors are used throughout. Region boundaries are FAO GAUL 2015.
