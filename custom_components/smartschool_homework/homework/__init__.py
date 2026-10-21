"""The reports' business logic: fetch from Smartschool, build the messages, render and print receipts.

Used by the Home Assistant integration (this folder's parent) and by the stand-alone app at the
top of the repo, which runs the same reports without Home Assistant (it puts the integration's
folder on sys.path and imports this as `homework`). So nothing here may import Home Assistant,
and everything around the reports (settings, logging, error reporting, scheduling, where the last
Results report is remembered) belongs to the integration or the app, not here.
"""
