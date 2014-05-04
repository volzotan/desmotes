# Desmotes

a simple tool for visualizing Misfit Shine activity tracker data.

![Thumbnail Website View](/readme/thumb.png?raw=true)


## Usage:

You must get hold of the database where the misfit app stores your activity data and drop it in the directory.

Either scrape them from your iPhone backup or copy via iTunes ( Apps > File Sharing > Misfit > Select Prometheus.sqlite from the list )

    python desmotes.py

If you have done several backups, the data will be merged if you run:

    python desmotes.py Prometheus1.sqlite Prometheus2.sqlite Prometheus3.sqlite