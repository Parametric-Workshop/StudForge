"""The Rebrickable Census: which real shapes exist, how much each is used, and coverage.

The names imported below are the census's API: everything a client may use.
A client writes "import census" and nothing more.

  import_snapshot()         a Rebrickable snapshot becomes the census database
  import_pinned_snapshot()  the same, for the snapshot the manifest records
  condense()                the census's part numbers become shapes
  report_coverage()         statuses, the census tree, the summary and the viewer
  import_state()            which snapshot the census holds
  condense_state()          whether it needs condensing
  releases_to_drop()        which published releases the thinning schedule drops

None of these decides whether it is needed: the client reads the two states
and decides. The code is laid out the way the architecture diagram draws it:

  cli.py        the client: reads the command line and calls the API
  importing/    the import operation, start to finish in run_import.py
  condensing/   the condense operation, start to finish in run_condense.py
  coverage/     the coverage operation, start to finish in run_coverage.py
  store/        the data: the census database, its archive, and where files are

Run it from the repo folder:  python3 -m census --help
"""

from census.condensing.run_condense import CondenseState, condense, condense_state
from census.coverage.run_coverage import report_coverage
from census.importing.archiving import releases_to_drop
from census.importing.run_import import (
    ImportState,
    import_pinned_snapshot,
    import_snapshot,
    import_state,
)
from census.importing.snapshot import SOURCE_FILES
from census.store.files import VIEWER_PATH

__all__ = [
    "SOURCE_FILES",
    "VIEWER_PATH",
    "CondenseState",
    "ImportState",
    "condense",
    "condense_state",
    "import_pinned_snapshot",
    "import_snapshot",
    "import_state",
    "releases_to_drop",
    "report_coverage",
]
