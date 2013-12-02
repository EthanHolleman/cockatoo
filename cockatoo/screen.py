import csv
import re
import logging
import json
from rdkit import Chem
from rdkit.Chem.rdMolDescriptors import GetMorganFingerprint

logger = logging.getLogger(__name__)

class Compound(object):
    """
    This class represents a chemcial compound used in a cocktail.

    """
    
    def __init__(self, name, conc, unit, ph=None):
        """
        A compound requires a name, concentration, and a unit. For example:
            sodium chloride, 1.0, M

        :param str name: Name of the compound
        :param float conc: Concentration of the compound
        :param str unit: Unit of the concentration (ex. M, % w/v)
        :param float ph: ph of the compound in solution
        :param float conc_max: Maximum concentration for the compound (default: None)
        :param str smiles: The SMILES represenation of the compound (default: None)
            
        """
        self.name = name
        self.conc = conc
        self.unit = unit
        self.ph = ph
        self.conc_min = None
        self.conc_max = None
        self.smiles = None
        self.cations = None
        self.anions = None
        self.ions_by_name = {}
        self.is_peg = False
        self.molecular_weight = False

    def has_cations(self):
        return self.cations is not None and len(self.cations) > 0

    def has_anions(self):
        return self.anions is not None and len(self.anions) > 0

    def is_nonsalt(self):
        return (self.anions is None or len(self.anions) == 0) and (self.cations is None or len(self.cations) == 0)

    def reprJSON(self):
        return self.__dict__

    def __str__(self):
        return "[ %s ]" % ", ".join(
            '%r' % i for i in [
                self.name,
                self.conc,
                self.unit,
                self.ph,
                self.smiles,
                self.is_peg,
                self.ions_by_name,
                self.conc_min,
                self.conc_max,
                self.molecular_weight
            ])


class Cocktail(object):
    """
    This class represents a cocktail.

    A cocktail is made of of one or more compounds.

    """

    def __init__(self, name, ph=None, components=None):
        """
        A cocktail requires a name and optionally a ph and an array of components.

        :param str name: Name of the cocktail
        :param float ph: Overall pH of the the cocktail (default: None)
        :param array components: An array of :class:`cockatoo.Compound` objects (default: [])
            
        """
        self.name = name
        self.ph = ph
        self.components = components if components is not None else []

    def __len__(self):
        """
        :returns: the number of components in the cocktail

        """
        return len(self.components)

    def add_compound(self, compound):
        """
        Add a compound to the cocktail.

        :param compound compound: The compound to add (:class:`cockatoo.Compound`)

        """
        self.components.append(compound)

    def map_by_name(self):
        """
        Return a map of compound conc and conc_max by name.

        :returns: dict where keys are compound names and values are [conc,conc_max]

        """
        name_map = {}
        for c in self.components:
            name_map[c.name] = c

        return name_map

    def cations(self):
        """
        Return a list of cation fragments from each compounds

        :returns: list of cations

        """
        cations = []
        for c in self.components:
            if c.has_cations():
                cations += c._cations

        return cations

    def anions(self):
        """
        Return a list of anion fragments from each compounds

        :returns: list of anions

        """
        anions = []
        for c in self.components:
            if c.has_anions():
                anions += c._anions

        return anions

    def ions(self):
        """
        Return a list of ions

        :returns: list of ions

        """
        ions = []
        for c in self.components:
            if c._mol is not None and (c.has_anions() or c.has_cations()):
                ions.append(c)

        return ions

    def nonsalts(self):
        """
        Return a list of nonsalts

        :returns: list of nonsalts

        """
        nonsalts = []
        for c in self.components:
            if c._mol is not None and not c.has_anions() and not c.has_cations():
                nonsalts.append(c)

        return nonsalts

    def all(self):
        nonsalts = []
        for c in self.components:
            if c._mol is not None:
                nonsalts.append(c)

        return nonsalts

    def reprJSON(self):
        return self.__dict__

    def __str__(self):
        return "[ %s ]" % ", ".join('%r' % i for i in [self.name,len(self),self.ph])

class Screen(object):
    """
    This class represents a macromolecular crystallization screen.

    A screen is made of of one or more cocktails.

    """

    def __init__(self, name, cocktails=None):
        """
        A screen requires a name and optionally an array of cocktails.

        :param str name: Name of the screen
        :param array cocktails: An array of :class:`cockatoo.Cocktail` objects (default: [])
            
        """
        self.name = name
        self.cocktails = cocktails if cocktails is not None else []

    def __len__(self):
        """
        :returns: the number of components in the cocktail

        """
        return len(self.cocktails)

    def add_cocktail(self, cocktail):
        """
        Add a cocktail to the screen.

        :param cocktail cocktail: The cocktail to add (:class:`cockatoo.Cocktail`)

        """
        self.cocktails.append(cocktail)

    def print_stats(self):
        """
        Print summary stats for the screen.

        """
        cmap = {}
        for cocktail in self.cocktails:
            for c in cocktail.components:
                cmap[c.name] = cmap.get(c.name, 0) + 1

        print "Name: %s" % self.name
        print "Wells: %s" % len(self)
        print "Distinct Compounds: %s" % len(cmap.keys())
        for k in sorted(cmap, key=cmap.get, reverse=True):
            print "%s: %s" % (k, cmap[k])

    def json(self):
        return json.dumps(self, cls=ComplexEncoder, encoding="utf8")


    def _set_ions(self, path):
        """
        Set ions from a given ion table.

        The component list of each cocktail is searched for matching ions from
        the given ion table.

        """
        ion_table = {}
        with open(path, 'rb') as csvfile:
            reader = csv.DictReader(csvfile, delimiter="\t")
            for row in reader:
                try:
                    row['_mol'] = Chem.MolFromSmiles(row['smiles'])
                except:
                    logger.critical("Invalid smiles format, failed to parse smiles for ion: %s" % row['name'])

                ion_table[row['name'].lower()] = row


        # Match based on substructure search
        for ck in self.cocktails:
            for cp in ck.components:
                cp.cations = []
                cp.anions = []
                self._set_mol_ions(cp, ion_table)

                # match ions by name for C6
                for m in re.split(r'[\s+,\-\/]+', cp.name):
                    if m in ion_table:
                        cp.ions_by_name[m] = True

        

    def _set_mol_ions(self, cp, ion_table):
        """
        Set ions from a given ion table based on substructure search

        The component list of each cocktail is searched for matching ions from
        the given ion table using the SMILES for each ion.

        """
        if cp.smiles is None: return
        mol = Chem.MolFromSmiles(cp.smiles)
        if mol is None: return

        for frag in Chem.GetMolFrags(mol, asMols=True):
            for s in ion_table:
                if frag.HasSubstructMatch(ion_table[s]['_mol']):
                    if ion_table[s]['type'] == 'c':
                        cp.cations.append(Chem.MolToSmiles(frag))
                    elif ion_table[s]['type'] == 'a':
                        cp.anions.append(Chem.MolToSmiles(frag))

    def _set_summary_stats(self, path):
        """
        Set summary data for each compound (ex. min,max,std of concentrations).

        """
        cols = ['conc_min', 'conc_max', 'molecular_weight']
        data = {}
        with open(path, 'rb') as csvfile:
            reader = csv.DictReader(csvfile, delimiter="\t")
            for row in reader:
                data[row['name'].lower()] = row
        
        for ck in self.cocktails:
            for cp in ck.components:
                if cp.name in data:
                    row = data[cp.name]
                    for key in cols:
                        if key in row and len(row[key]) > 0:
                            setattr(cp, key, float(row[key]))
                        else:
                            setattr(cp, key, None)
                            logger.critical("Missing summary statistic '%s' for compound: %s" % (key, cp.name))

                    if 'smiles' in row and len(row['smiles']) > 0:
                        cp.smiles = row['smiles'].encode("utf8")
                        try:
                            mol = Chem.MolFromSmiles(cp.smiles)
                        except:
                            logger.critical("Invalid smiles format, failed to parse smiles for compound: %s" % cp.name)
                    else:
                        logger.critical("Missing smiles data for compound: %s" % cp.name)
                else:
                    logger.critical("Missing summary data for compound: %s" % cp.name)

    def reprJSON(self):
        return self.__dict__

    def __str__(self):
        return "[ %s ]" % ", ".join([self.name,str(len(self))])


# From http://stackoverflow.com/a/5165421
class ComplexEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj,'reprJSON'):
            return obj.reprJSON()
        else:
            return json.JSONEncoder.default(self, obj)

def parse_json(path):
    """
    Parse a screen in JSON format.

    It's assumed the screen was first converted from CSV using the
    'cockatoo-convert' command. If not, ensure all required attributes are
    present in JSON data.

    :param str name: Name of the screen
    :param str path: Path to file

    :returns: The screen (:class:`cockatoo.Screen`)
        
    """
    screen_json = None
    with open(path, 'rb') as f:
        screen_json = json.load(f, encoding="utf8")

    screen = Screen(screen_json['name'])
    if 'name' not in screen_json:
        logger.critical('Invalid json, missing screen name')
        return None

    for ck in screen_json['cocktails']:
        if 'name' not in ck:
            logger.critical('Invalid json, missing cocktail name. Skipping')
            continue

        cocktail = Cocktail(ck['name'])
        for key in cocktail.__dict__.keys():
            if key == 'components': continue
            if key not in ck:
                logger.critical('Invalid json, missing cocktail attribute %s: ' % key)
                continue
            setattr(cocktail, key, ck[key])

        for cp in ck['components']:
            compound = Compound('dummy', 1.0, 'M')
            for key in compound.__dict__.keys():
                if key not in cp:
                    logger.critical('Invalid json, missing compound attribute %s: ' % key)
                    continue
                setattr(compound, key, cp[key])

            compound._mol = None
            compound._ecfp = None
            if compound.smiles is not None:
                try:
                    compound._mol = Chem.MolFromSmiles(compound.smiles.encode("utf8"))
                    compound._ecfp = GetMorganFingerprint(compound._mol,2)
                except:
                    logger.critical("Invalid smiles format, failed to parse smiles for compound: %s" % compound.name)

            if compound.has_cations():
                compound._cations = [Chem.MolFromSmiles(x.encode("utf8")) for x in compound.cations]
            if compound.has_anions():
                compound._anions = [Chem.MolFromSmiles(x.encode("Utf8")) for x in compound.anions]

            cocktail.add_compound(compound)

        screen.add_cocktail(cocktail)
    
    return screen

def parse_csv(name, path):
    """
    Parse a screen in CSV format.

    :param str name: Name of the screen
    pparam str path: Path to file

    :returns: The screen (:class:`cockatoo.Screen`)
        
    """
    screen = Screen(name)

    with open(path, 'rb') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            # Skip comments
            if re.search(r'^#', row[0]): continue
            cocktail = _parse_cocktail(row)
            if cocktail is not None:
                screen.add_cocktail(cocktail)

    return screen


def _parse_float(val):
    try:
        val = float(val)
    except:
        val = None

    return val

def _parse_cocktail(row):
    """
    Private function to parse cocktail data from CSV row.

    The format for columns is assumed to be:

    name,overall_ph,[conc,unit,name,ph]*
    
     *repeated 1 or more times for each compound

    It's common to put the buffer as the first compound which will be used as
    the overall ph.

    See test screens for example of CSV format.

    :param str name: Name of the screen
    :param str path: Path to file

    :returns: The screen (:class:`cockatoo.Screen`)
        
    """
    cocktail = Cocktail(
        row[0].strip(),
        _parse_float(re.sub(r'(?i)ph\s*','', row[1].strip()))
    )

    if len(cocktail.name) <= 0:
        logger.warning('Malformed line, missing cocktail name: %s' % (row))
        return None

    ph_vals = []
    compounds = row[2:]
    if not len(compounds) % 4 == 0:
        logger.warning('Malformed line: %s' % (row))

    index = 0
    while index < len(compounds):
        compound = Compound(
            compounds[index+2].strip(),
            _parse_float(compounds[index].strip()),
            compounds[index+1].strip(),
            _parse_float(re.sub(r'(?i)ph\s*','', compounds[index+3].strip()))
        )

        if len(compound.name) > 0:
            compound.name = compound.name.lower()
        else:
            logger.warning('Malformed line, missing compound name: %s' % (row))
            return None

        if compound.conc is None:
            logger.warning('Malformed line, missing concentration value: %s' % (row))
            return None

        if compound.ph is not None:
            ph_vals.append(compound.ph)

        matches = re.search(r'^((?:peg|polyethylene\sglycol)[^\d]+)(\d+)', compound.name)
        if matches:
            compound.is_peg = True

        cocktail.add_compound(compound)

        index += 4

    ph = list(set(ph_vals))
    if cocktail.ph is not None:
        pass
    elif len(ph) == 1:
        cocktail.ph = ph[0]
    elif len(ph) > 1:
        logger.info("Multiple pH values found using the buffer (first one in list): %s" % cocktail)
        cocktail.ph = ph_vals[0]

    return cocktail