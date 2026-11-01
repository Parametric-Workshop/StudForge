"""The FreeCAD generator: builds the block family's master body, and checks it.

Its code needs FreeCAD's own Python, so it runs in two halves: the client in
ordinary Python, and everything else inside the FreeCAD it starts.

  cli.py             the client: reads the command line, finds FreeCAD, starts it
  inside_freecad.py  the API: the command FreeCAD is started with, verify
  verifying/         the verify operation, start to finish in run_verify.py
  families/          the models: each family's master body and rules
  store/             the data: nominal values, print offsets, profiles, part files

Run it from the repo folder:  python3 -m freecad_generator --help
"""
