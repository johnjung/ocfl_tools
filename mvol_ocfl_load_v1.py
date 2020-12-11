#!/usr/bin/env python
"""Usage: mvol_ocfl_load_v1.py --local-root=<path> [--dry-run] <identifier>
"""

import datetime, hashlib, json, os, random, re, shutil, sqlite3, subprocess, sys
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

def build_initial_inventory(file_path, identifier, user_name, user_address, message):
    inventory = {
        "digestAlgorithm": "sha512",
        "head": "v1",
        "id": identifier,
        "manifest": {},
        "type": "https://ocfl.io/1.0/spec/#inventory",
        "versions": {
            "v1": {
                "created": datetime.datetime.utcnow().isoformat() + 'Z',
                "message": message,
                "state":{},
                "user": {
                    "address": user_address,
                    "name": user_name
                }
            }
        }
    }

    for root, dirs, files in os.walk(file_path):
        for filename in files:
            short_pathname = re.sub('^.*/v1/content/', '', root + os.sep + filename)
            with open(root + os.sep + filename, 'rb') as f:
                h = hashlib.sha512(f.read()).hexdigest()
            if not h in inventory['manifest']:
                inventory['manifest'][h] = []
            inventory['manifest'][h].append('v1/content/' + short_pathname)
            if not h in inventory['versions']['v1']['state']:
                inventory['versions']['v1']['state'][h] = []
            inventory['versions']['v1']['state'][h].append(short_pathname)

    return inventory

def build_sidecar(file_path):
    with open(file_path, 'rb') as f:
        return hashlib.sha512(f.read()).hexdigest()

def save_sidecar(file_path):
    with open('{}.sha512'.format(file_path), 'w') as f:
        f.write('{} inventory.json\n'.format(build_sidecar(file_path)))


class NoidManager():
    """A class to manage NOIDS for digital collections."""
    def __init__(self, pair_tree_root):
        self.pair_tree_root = pair_tree_root
        self.extended_digits = '0123456789bcdfghjkmnpqrstvwxz'

    def list(self):
        """Get a list of the NOIDs present."""
    
        identifiers = []
        for root, dirs, files in os.walk(self.pair_tree_root):
            for file in files:
                if file in ('0=ocfl_object_1.0',):
                    identifiers.append(root[len(self.pair_tree_root):].replace(os.sep, ''))
        return identifiers

    def generate_check_digit(self, noid):
        """Multiply each characters ordinal value by it's position, starting at
           position 1. Sum the products. Then do modulo 29 to get the check digit
           in extended characters."""
        s = 0
        p = 1
        for c in noid:
            if self.extended_digits.find(c) > -1:
                s += (self.extended_digits.find(c) * p)
            p += 1
        return self.extended_digits[s % len(self.extended_digits)]

    def test_noid_check_digit(self, noid):
        """Use this for NOIDs that came from other sources."""
        return self.generate_check_digit(self.extended_digits, noid[:-1]) == noid[-1:]

    def create(self):
        """create a UChicago NOID in the form 'b2.reedeedeedk', where: 
         
           e is an extended digit, 
           d is a digit, 
           and k is a check digit.
    
           Note that all UChicago Library NOIDs start with the prefix "b2", so
           that's hardcoded into this function."""
    
        noid = [
            'b',
            '2',
            random.choice(self.extended_digits),
            random.choice(self.extended_digits),
            random.choice(self.extended_digits[:10]),
            random.choice(self.extended_digits),
            random.choice(self.extended_digits),
            random.choice(self.extended_digits[:10]),
            random.choice(self.extended_digits),
            random.choice(self.extended_digits),
            random.choice(self.extended_digits[:10])
        ]
        noid.append(self.generate_check_digit(''.join(noid)))
        return ''.join(noid)

    def path(self, noid):
        """split the noid into two character directories."""
        return os.sep.join([noid[i] + noid[i+1] for i in range(0, len(noid), 2)])

    def noid_is_unique(self, noid, path):
        """Check to see if ARKS with that noid exist in our system. 
           Returns true if the NOID is unique in our system. 
           (Note that with 600B possible NOIDs, it is very unlikely that this
           function will ever return False.)"""
        return noid not in self.list(path)


if __name__ == "__main__":
    options = docopt(__doc__)

    conn = sqlite3.connect('/data/s4/jej/ark_data.db')
    c = conn.cursor()
    ark_data = '/data/digital_collections/ark_data'

    nm = NoidManager(ark_data)

    noid = nm.create()
    ark = 'ark:/61001/{}'.format(noid)
    print(ark)

    pair_tree_directory = '{}/{}'.format(
        ark_data,
        os.sep.join([noid[c:c+2] for c in range(0, len(noid), 2)])
    )
    pair_tree_directory_parent = os.path.abspath(os.path.join(pair_tree_directory, os.pardir))
    pair_tree_directory_leaf = os.path.basename(os.path.normpath(pair_tree_directory))

    mvol_dir = ''.join((
        options['--local-root'],
        os.sep,
        options['<identifier>'].replace('-', os.sep),
    ))

    tmp_dir = '/data/digital_collections/IIIF/tmp/{}'.format(
        pair_tree_directory_leaf
    )

    # be sure that there isn't both an ALTO and XML directory. 
    counts = 0
    for d in ('ALTO', 'XML'):
        if os.path.isdir(os.sep.join((mvol_dir, d))):
            counts += 1
    assert counts <= 1

    # be sure all object directories contain the name number of files.
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

    if not options['--dry-run']:
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir)
        os.makedirs(tmp_dir)

    # create <objdir>/v1/
    if not options['--dry-run']:
        os.makedirs(
            os.path.join(
                tmp_dir,
                'v1'
            )
        )

    # create <objdir>/0=ocfl_object_1.0
    if not options['--dry-run']:
        with open(
            os.path.join(
                tmp_dir,
                '0=ocfl_object_1.0'
            ),
            'w'
        ) as f:
            f.write('ocfl_object_1.0\n')

    # create <objdir>/v1/content
    if not options['--dry-run']:
        os.makedirs(
            os.path.join(
                tmp_dir,
                'v1',
                'content'
            )
        )

    # file.dc.xml - add namespaces and pretty-print
    with open(os.sep.join((
        mvol_dir,
        '{}.dc.xml'.format(options['<identifier>'])
    ))) as f:
        try:
            orig_dc = ElementTree.parse(f)
        except ElementTree.ParseError:
            sys.stdout.write('XML error on {}.\n'.format(options['<identifier>']))
    ns_dc = ElementTree.Element('metadata')
    for el in ('title', 'date', 'identifier', 'description'):
        ns_el = ElementTree.SubElement(
            ns_dc,
            '{http://purl.org/dc/elements/1.1/}' + el
        )
        try:
            ns_el.text = orig_dc.find(el).text
            if orig_dc.find(el).text == '':
                sys.stdout.write('XML element error on {}.\n'.format(options['<identifier>']))
        except NameError:
            sys.stdout.write('XML element error on {}.\n'.format(options['<identifier>']))

    xml_indent(ns_dc)

    if not options['--dry-run']:
        with open(os.sep.join((
            tmp_dir,
            'v1',
            'content',
            'file.dc.xml'
        )), 'w') as f:
            f.write('<?xml version="1.0"?>\n')
            f.write(ElementTree.tostring(ns_dc, encoding='utf-8').decode('utf-8'))

    # file.pdf
    if options['--dry-run']:
        with open(
            os.sep.join((
                mvol_dir,
                '{}.pdf'.format(options['<identifier>'])
            ))
        ) as f:
            pass
    else:
        shutil.move(
            os.sep.join((
                mvol_dir,
                '{}.pdf'.format(options['<identifier>'])
            )),
            os.sep.join((
                tmp_dir,
                'v1',
                'content',
                'file.pdf'
            ))
        )

    # file.struct.txt
    if options['--dry-run']:
        with open(
            os.sep.join((
                mvol_dir,
                '{}.struct.txt'.format(options['<identifier>'])
            ))
        ) as f:
            pass
    else:
        shutil.move(
            os.sep.join((
                mvol_dir,
                '{}.struct.txt'.format(options['<identifier>'])
            )),
            os.sep.join((
                tmp_dir,
                'v1',
                'content',
                'file.struct.txt'
            ))
        ) 

    # object directories

    # get a count of the number of files.
    count = 0
    for fname in os.listdir(os.sep.join((mvol_dir, 'TIFF'))):
        if fname.endswith('.tif'):
            count += 1

    if not options['--dry-run']:
        for n in range(count):
            os.mkdir(os.sep.join((
                tmp_dir,
                'v1',
                'content',
                '{:08d}'.format(n + 1)
            )))

    # alto, pos, tif, xml

    if not options['--dry-run']:
        for d, ext in {
            'ALTO': 'xml',
            'POS': 'pos',
            'TIFF': 'tif',
            'XML': 'xml'
        }.items():
            try:
                for n, fname in enumerate(sorted(os.listdir(os.sep.join((
                    mvol_dir,
                    d
                ))))):
                    shutil.move(
                        os.sep.join((
                            mvol_dir,
                            d,
                            fname
                        )),
                        os.sep.join((
                            tmp_dir,
                            'v1',
                            'content',
                            '{:08d}'.format(n + 1),
                            'file.{}'.format(ext)
                        ))
                    )
            except FileNotFoundError:
                continue

    # <objdir>/inventory.json
    # <objdir>/v1/inventory.json
    inventory = build_initial_inventory(
        os.path.join(
            tmp_dir,
            'v1',
            'content'
        ),
        ark,
        'John Jung',
        'mailto:jej@uchicago.edu',
        'Initial commit.'
    )

    for file_path in (
        os.path.join(
            tmp_dir,
            'inventory.json'
        ),
        os.path.join(
            tmp_dir,
            'v1',
            'inventory.json'
        )
    ):
        with open(file_path, 'w') as f:
            f.write(
                json.dumps(
                    inventory,
                    indent=2,
                    sort_keys=True
                )
            )

    # <objdir>/inventory.json.sha512
    # <objdir>/v1/inventory.json.sha512
    save_sidecar(os.path.join(
        tmp_dir,
        'inventory.json'
    ))
    save_sidecar(os.path.join(
        tmp_dir,
        'v1', 
        'inventory.json'
    ))

    # make pair tree directory.
    if not options['--dry-run']:
        if not os.path.exists(pair_tree_directory_parent):
            os.makedirs(pair_tree_directory_parent)

    # move this directory into place in the pair tree.
    if not options['--dry-run']:
        shutil.move(
            tmp_dir,
            pair_tree_directory_parent
        )

    # update the database.
    if not options['--dry-run']:
        c.execute('INSERT INTO arks VALUES (?, ?, ?)', ('http://lib.uchicago.edu/digital_collections/campub', ark, options['<identifier>']))
        conn.commit()
