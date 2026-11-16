"""The FreeCAD generator: builds each shape's nominal FreeCAD and STEP file.

Its code needs FreeCAD's own Python, so it runs in two halves: the client in
ordinary Python, and everything else inside the FreeCAD it starts.

  cli.py             the client: reads the command line, finds FreeCAD, starts it
  inside_freecad.py  the API: the commands FreeCAD is started with, generate and verify
  generating/        the generate operation, start to finish in run_generate.py
  verifying/         the verify operation, start to finish in run_verify.py
  families/          the models both operations use: each family's master body and rules
  store/             the data: nominal values, print offsets, profiles, part files

Run it from the repo folder:  python3 -m freecad_generator --help
"""
