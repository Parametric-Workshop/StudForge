"""The Rebrickable Census: which real shapes exist, how much each is used, and coverage.

Laid out the way the architecture diagram draws it:

  cli.py        the client: reads the command line and calls the API
  api.py        the Census service API: import_snapshot(), condense(), coverage()
  importing/    the import operation: a Rebrickable snapshot becomes the census
  condensing/   the condense operation: part numbers become shapes
  coverage/     the coverage operation: statuses, the census tree and the viewer
  store/        the data: the census database's API, its archive, and where files are

Run it from the repo folder:  python3 -m census --help
"""
