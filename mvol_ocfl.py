#!/usr/bin/env python
"""Usage: mvol_ocfl.py --local-root=<path> <identifier> <dirname> [--force]
"""

import os, shutil, sys
from docopt import docopt

import xml.etree.ElementTree as ElementTree

# TODO
# this script curently assumes that the mvol directory it pulls from
# is valid. it should check the validation db to confirm that the 
# directory is valid before beginning.

# need triples to insert into OCFL.

def xml_indent(el, level=0):
    i = '\n' + level * '  '
    if len(el):
        if not el.text or not el.text.strip():
            el.text = i + '  '
        if not el.tail or not el.tail.strip():
            el.tail = i
        for el in el:
            xml_indent(el, level+1)
        if not el.tail or not el.tail.strip():
            el.tail = i
    else:
        if level and (not el.tail or not el.tail.strip()):
            el.tail = i

if __name__ == "__main__":
    options = docopt(__doc__)

    mvol_dir = ''.join((
        options['--local-root'],
        os.sep,
        options['<identifier>'].replace('-', os.sep),
    ))

    # if <dirname> is inside --local-root, then bail out. this is a
    # naive check- it doesn't take symlinks into consideration, or other
    # ways <dirname> might actually be inside --local-root.
    if (os.path.abspath(options['<dirname>']).startswith(
        os.path.abspath(options['--local-root']) 
    )):
        sys.stdout.write('{} appears to be inside {}. quitting.\n'.format(
            options['<dirname>'],
            options['--local-root']
        ))
        sys.exit()

    if options['--force'] and os.path.isdir(options['<dirname>']):
        shutil.rmtree(options['<dirname>'])

    os.makedirs(options['<dirname>'])

    # file.dc.xml - add namespaces and pretty-print
    with open(os.sep.join((
        mvol_dir,
        '{}.dc.xml'.format(options['<identifier>'])
    ))) as f:
        orig_dc = ElementTree.parse(f)
    ns_dc = ElementTree.Element('metadata')
    for el in ('title', 'date', 'identifier', 'description'):
        ns_el = ElementTree.SubElement(
            ns_dc,
            '{http://purl.org/dc/elements/1.1/}' + el
        )
        ns_el.text = orig_dc.find(el).text
    xml_indent(ns_dc)

    with open(os.sep.join((
        options['<dirname>'],
        'file.dc.xml'
    )), 'w') as f:
        f.write('<?xml version="1.0"?>\n')
        f.write(ElementTree.tostring(ns_dc, encoding='utf-8').decode('utf-8'))

    # file.pdf
    shutil.copy(
        os.sep.join((
            mvol_dir,
            '{}.pdf'.format(options['<identifier>'])
        )),
        os.sep.join((
            options['<dirname>'],
            'file.pdf'
        ))
    )

    # file.struct.txt
    shutil.copy(
        os.sep.join((
            mvol_dir,
            '{}.struct.txt'.format(options['<identifier>'])
        )),
        os.sep.join((
            options['<dirname>'],
            'file.struct.txt'
        ))
    )

    # file.ttl (TODO)



    # object directories

    # confirm that all relevant object directories contain the same
    # number of objects.
    counts = set()
    for d, ext in {
        'ALTO': 'xml',
        'POS': 'pos',
        'TIFF': 'tif',
        'XML': 'xml'
    }.items():
        try:
            count = 0
            for fname in os.listdir(os.sep.join((mvol_dir, d))):
                if fname.endswith('.' + ext):
                    count += 1
            counts.add(count)
        except FileNotFoundError:
            continue
           
    assert len(counts) == 1

    for n in range(list(counts)[0]):
        os.mkdir(os.sep.join((
            options['<dirname>'],
            '{:08d}'.format(n + 1)
        )))

    # alto, pos, tif, xml

    # be sure that there isn't both an ALTO and XML directory. 
    counts = 0
    for d in ('ALTO', 'XML'):
        if os.path.isdir(os.sep.join((mvol_dir, d))):
            counts += 1
    assert counts <= 1

    for d, ext in {
        'ALTO': 'xml',
        'POS': 'pos',
        'TIFF': 'tif',
        'XML': 'xml'
    }.items():
        try:
            for n, fname in enumerate(os.listdir(os.sep.join((
                mvol_dir,
                d
            )))):
                shutil.copy(
                    os.sep.join((
                        mvol_dir,
                        d,
                        fname
                    )),
                    os.sep.join((
                        options['<dirname>'],
                        '{:08d}'.format(n + 1),
                        'file.{}'.format(ext)
                    ))
                )
        except FileNotFoundError:
            continue

    # file.ttl
