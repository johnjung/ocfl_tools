#!/usr/bin/env python
"""Usage: mvol_ocfl.py --local-root=<path> <identifier> <dirname>
"""

from docopt import docopt

if __name__ == "__main__":
    options = docopt(__doc__)
    print(options)




# need file.dc.xml.
# it should match xmllint --format-
#  xml declaration
#  pretty printing
# it should have namespaces for DC elements.

# file.pdf

# file.struct.txt

# file.ttl

# also, a sequence of 8 digit object directories.

# each should have:
#  file.tif
#  file.ttl
#  one or more of file.xml / file.pos
