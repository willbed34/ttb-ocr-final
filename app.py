"""
Alcohol Label Verifier - STREAMLINED VERSION
Single-pass OCR + expanded correction dictionary + fuzzy matching.
No OpenCV dependency. Target: <5s processing time.
"""

import os
import re
import csv
import io
import uuid
import time
from flask import Flask, request, render_template_string, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import pytesseract
from difflib import SequenceMatcher

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

GOVERNMENT_WARNING = """GOVERNMENT WARNING: (1) According to the Surgeon General, women should not drink alcoholic beverages during pregnancy because of the risk of birth defects. (2) Consumption of alcoholic beverages impairs your ability to drive a car or operate machinery, and may cause health problems."""

# ============================================================================
# EXPANDED OCR ERROR CORRECTION DICTIONARY
# ============================================================================

OCR_CORRECTIONS = {
    # === BEER BRANDS ===
    # Michelob variations
    'maheleb': 'michelob', 'mabeleb': 'michelob', 'maheiob': 'michelob',
    'mahclob': 'michelob', 'mlchelob': 'michelob', 'm1chelob': 'michelob',
    'miche1ob': 'michelob', 'mictieleb': 'michelob', 'miibetob': 'michelob',
    'cmlicheelob': 'michelob', 'mitehelob': 'michelob', 'micheleb': 'michelob',
    'micheiob': 'michelob', 'michelab': 'michelob', 'mlcheleb': 'michelob',
    'micheloh': 'michelob', 'michclob': 'michelob', 'micheieb': 'michelob',
    'rnichelob': 'michelob', 'miehelob': 'michelob', 'micheob': 'michelob',
    'miheleb': 'michelob',
    # Ultra variations
    'uttra': 'ultra', 'u1tra': 'ultra', 'uitra': 'ultra', 'ultr4': 'ultra',
    'uiltra': 'ultra', 'uitr4': 'ultra', 'ulira': 'ultra', 'utra': 'ultra',
    # Budweiser variations
    'budwelser': 'budweiser', 'budwe1ser': 'budweiser', 'budwiser': 'budweiser',
    'budwieser': 'budweiser', 'budwelsr': 'budweiser', 'budweisar': 'budweiser',
    'budwelsr': 'budweiser', 'budwaser': 'budweiser', 'budw3iser': 'budweiser',
    # Bud Light variations
    'bud1ight': 'bud light', 'budlight': 'bud light', 'bud1ighi': 'bud light',
    'budilght': 'bud light', 'bud llght': 'bud light',
    # Coors variations
    'c00rs': 'coors', 'co0rs': 'coors', 'coor5': 'coors', 'cooors': 'coors',
    # Miller variations
    'mi11er': 'miller', 'miiler': 'miller', 'm1ller': 'miller', 'mlller': 'miller',
    # Corona variations
    'c0rona': 'corona', 'cor0na': 'corona', 'carona': 'corona', 'corono': 'corona',
    # Heineken variations
    'helneken': 'heineken', 'he1neken': 'heineken', 'hieneken': 'heineken',
    'heiniken': 'heineken', 'heinekn': 'heineken', 'hienken': 'heineken',
    # Stella Artois variations
    'ste11a': 'stella', 'stelia': 'stella', 'steila': 'stella',
    'art0is': 'artois', 'artols': 'artois', 'artios': 'artois',
    # Modelo variations
    'mode1o': 'modelo', 'modela': 'modelo', 'm0delo': 'modelo',
    # Guinness variations
    'gulnness': 'guinness', 'gu1nness': 'guinness', 'guiness': 'guinness',
    'guinnes': 'guinness', 'guinnss': 'guinness', 'guinn3ss': 'guinness',
    # Samuel Adams variations
    'samue1': 'samuel', 'sarnuel': 'samuel', 'samuei': 'samuel',
    # Pabst variations
    'pabsi': 'pabst', 'pa8st': 'pabst', 'p4bst': 'pabst',
    # Blue Ribbon
    'b1ue': 'blue', 'biue': 'blue', 'bule': 'blue',
    'rlbbon': 'ribbon', 'r1bbon': 'ribbon', 'ribben': 'ribbon',
    # Natural Light/Natty
    'natura1': 'natural', 'naturaal': 'natural', 'naturai': 'natural',
    '1ight': 'light', 'ilght': 'light', 'lighi': 'light', 'l1ght': 'light',
    # Yuengling
    'yueng1ing': 'yuengling', 'yuengllng': 'yuengling', 'yuengiing': 'yuengling',
    # Sierra Nevada
    'slerra': 'sierra', 's1erra': 'sierra', 'siarra': 'sierra', 'sterra': 'sierra',
    'nevado': 'nevada', 'nevad0': 'nevada', 'n3vada': 'nevada',
    # Lagunitas
    'lagunltas': 'lagunitas', '1agunitas': 'lagunitas', 'lagunits': 'lagunitas',
    # Dogfish
    'dogf1sh': 'dogfish', 'd0gfish': 'dogfish', 'dogfsh': 'dogfish',
    # Stone
    'st0ne': 'stone', 'ston3': 'stone',
    # Founders
    'f0unders': 'founders', 'found3rs': 'founders', 'foundrs': 'founders',
    # Bell's
    'be11s': 'bells', "bell's": 'bells', 'bel1s': 'bells',
    
    # === WINE BRANDS ===
    # Barefoot
    'baref00t': 'barefoot', 'barefool': 'barefoot', 'barefot': 'barefoot',
    # Yellow Tail
    'ye11ow': 'yellow', 'yeilow': 'yellow', 'yel1ow': 'yellow',
    'tal1': 'tail', 'taii': 'tail',
    # Sutter Home
    'suiter': 'sutter', 'suttr': 'sutter', 'suttter': 'sutter',
    # Franzia
    'franzla': 'franzia', 'franz1a': 'franzia', 'franza': 'franzia',
    # Woodbridge
    'w00dbridge': 'woodbridge', 'woodbrldge': 'woodbridge', 'woodbridg': 'woodbridge',
    # Kendall Jackson
    'kenda11': 'kendall', 'kendal1': 'kendall', 'kendaii': 'kendall',
    'jacks0n': 'jackson', 'jckson': 'jackson', 'jacksn': 'jackson',
    # Robert Mondavi
    'r0bert': 'robert', 'rob3rt': 'robert', 'robart': 'robert',
    'm0ndavi': 'mondavi', 'mondav1': 'mondavi', 'mondavl': 'mondavi',
    # Beringer
    'ber1nger': 'beringer', 'beringr': 'beringer', 'beringar': 'beringer',
    # Gallo
    'ga11o': 'gallo', 'galio': 'gallo', 'gall0': 'gallo',
    # Apothic
    'apoth1c': 'apothic', 'ap0thic': 'apothic', 'apothlc': 'apothic',
    # Josh Cellars
    'j0sh': 'josh', 'jash': 'josh',
    'ce11ars': 'cellars', 'cellar5': 'cellars', 'cellrs': 'cellars',
    # La Crema
    '1a': 'la', 'l4': 'la',
    'cr3ma': 'crema', 'crem4': 'crema',
    # Caymus
    'caymu5': 'caymus', 'cayrnus': 'caymus', 'cayrnus': 'caymus',
    # Silver Oak
    'si1ver': 'silver', 'sliver': 'silver', 's1lver': 'silver',
    '0ak': 'oak', 'oa1k': 'oak',
    # Opus One
    '0pus': 'opus', 'opu5': 'opus',
    '0ne': 'one', 'on3': 'one',
    
    # === SPIRITS BRANDS ===
    # Jack Daniels
    'danie1s': 'daniels', 'danlels': 'daniels', 'danielss': 'daniels',
    'dani3ls': 'daniels',
    # Jim Beam
    'j1m': 'jim', 'jlm': 'jim',
    'b3am': 'beam', 'bearn': 'beam',
    # Johnnie Walker
    'johnn1e': 'johnnie', 'johnnie': 'johnnie', 'johnnle': 'johnnie',
    'wa1ker': 'walker', 'waker': 'walker', 'walkar': 'walker',
    # Crown Royal
    'cr0wn': 'crown', 'crwn': 'crown', 'crawn': 'crown',
    'roya1': 'royal', 'royai': 'royal', 'rayal': 'royal',
    # Jameson
    'james0n': 'jameson', 'jarneson': 'jameson', 'jameson': 'jameson',
    # Hennessy
    'henness1': 'hennessy', 'hennessey': 'hennessy', 'henesy': 'hennessy',
    'hennssy': 'hennessy', 'hennesey': 'hennessy',
    # Grey Goose
    'gr3y': 'grey', 'groy': 'grey',
    'g00se': 'goose', 'go0se': 'goose', 'gose': 'goose',
    # Absolut
    'abso1ut': 'absolut', 'absolui': 'absolut', 'absalut': 'absolut',
    # Smirnoff
    'smlrnoff': 'smirnoff', 'sm1rnoff': 'smirnoff', 'smirnof': 'smirnoff',
    'smirn0ff': 'smirnoff',
    # Tito's
    'tit0s': 'titos', "tito's": 'titos', 'tltos': 'titos',
    # Patron
    'patr0n': 'patron', 'pairon': 'patron', 'patrn': 'patron',
    # Don Julio
    'd0n': 'don', 'dan': 'don',
    'ju1io': 'julio', 'jull0': 'julio', 'juli0': 'julio',
    # Casamigos
    'casamig0s': 'casamigos', 'casarnigos': 'casamigos', 'casamgos': 'casamigos',
    # Captain Morgan
    'capta1n': 'captain', 'captian': 'captain', 'captln': 'captain',
    'm0rgan': 'morgan', 'margan': 'morgan', 'morgn': 'morgan',
    # Bacardi
    'bacardl': 'bacardi', 'bacard1': 'bacardi', 'barcadi': 'bacardi',
    # Malibu
    'ma1ibu': 'malibu', 'mallbu': 'malibu', 'mal1bu': 'malibu',
    
    # === PRODUCERS/BREWERIES ===
    # Anheuser-Busch
    'anhueser': 'anheuser', 'anheusur': 'anheuser', 'anheuer': 'anheuser',
    'anheuser-busck': 'anheuser-busch', 'anheuser-bush': 'anheuser-busch',
    'busch': 'busch', 'busck': 'busch', 'bu5ch': 'busch',
    # MillerCoors
    'mi11ercoors': 'millercoors', 'millercoor5': 'millercoors',
    # Diageo
    'diage0': 'diageo', 'd1ageo': 'diageo', 'diagao': 'diageo',
    # Constellation
    'conste11ation': 'constellation', 'constelation': 'constellation',
    # Pernod Ricard
    'pern0d': 'pernod', 'pernad': 'pernod',
    'r1card': 'ricard', 'rlcard': 'ricard',
    # Brown Forman
    'br0wn': 'brown', 'brwn': 'brown',
    'f0rman': 'forman', 'forrnan': 'forman',
    
    # === WINE/BEER TYPES ===
    # Lager
    '1ager': 'lager', 'iager': 'lager', 'lag3r': 'lager', 'lagr': 'lager',
    # Pilsner
    'pi1sner': 'pilsner', 'pilsnar': 'pilsner', 'plisner': 'pilsner',
    # Ale
    'a1e': 'ale', 'aie': 'ale',
    # IPA
    '1pa': 'ipa', 'lpa': 'ipa',
    # Stout
    'st0ut': 'stout', 'siout': 'stout', 'stoui': 'stout',
    # Porter
    'p0rter': 'porter', 'portr': 'porter', 'porier': 'porter',
    # Wheat
    'wh3at': 'wheat', 'wheal': 'wheat',
    # Cabernet
    'cabern3t': 'cabernet', 'cabernei': 'cabernet', 'cabarnet': 'cabernet',
    'cabernett': 'cabernet',
    # Sauvignon
    'sauvlgnon': 'sauvignon', 'sauvign0n': 'sauvignon', 'sauvignan': 'sauvignon',
    'sauv1gnon': 'sauvignon',
    # Chardonnay
    'chardonn4y': 'chardonnay', 'chardannay': 'chardonnay', 'chardonay': 'chardonnay',
    'chardonnav': 'chardonnay',
    # Pinot
    'pin0t': 'pinot', 'plnot': 'pinot', 'pnot': 'pinot',
    # Noir
    'n0ir': 'noir', 'nolr': 'noir',
    # Grigio
    'grig1o': 'grigio', 'grlgio': 'grigio', 'grigl0': 'grigio',
    # Merlot
    'merl0t': 'merlot', 'merloi': 'merlot', 'meriot': 'merlot',
    # Riesling
    'r1esling': 'riesling', 'riesiing': 'riesling', 'riesllng': 'riesling',
    # Moscato
    'moscat0': 'moscato', 'mascato': 'moscato', 'moscoto': 'moscato',
    # Zinfandel
    'z1nfandel': 'zinfandel', 'zinfande1': 'zinfandel', 'zlnfandel': 'zinfandel',
    # Malbec
    'ma1bec': 'malbec', 'malbac': 'malbec', 'maibec': 'malbec',
    # Bourbon
    'bourb0n': 'bourbon', 'bourban': 'bourbon', 'bourbn': 'bourbon',
    # Whiskey/Whisky
    'wh1skey': 'whiskey', 'whlskey': 'whiskey', 'whisky': 'whiskey',
    'whisk3y': 'whiskey',
    # Vodka
    'v0dka': 'vodka', 'vodko': 'vodka', 'vdka': 'vodka',
    # Tequila
    'tequ1la': 'tequila', 'tequlia': 'tequila', 'teqila': 'tequila',
    # Rum
    'rurn': 'rum', 'rurn': 'rum',
    # Gin
    'g1n': 'gin', 'gln': 'gin',
    # Brandy
    'br4ndy': 'brandy', 'brandv': 'brandy',
    # Cognac
    'c0gnac': 'cognac', 'cagnac': 'cognac', 'cognc': 'cognac',
    
    # === VOLUME/ALCOHOL CONTENT ===
    'a1c': 'alc', 'aic': 'alc', 'a1c.': 'alc.', 'alcc': 'alc',
    'vo1': 'vol', 'voi': 'vol', 'v0l': 'vol', 'vo1.': 'vol.',
    'o2': 'oz', '02': 'oz', 'oz.': 'oz', '0z': 'oz', '07': 'oz', 'o7': 'oz',
    'f1': 'fl', 'fi': 'fl', 'fl.': 'fl',
    'm1': 'ml', 'mi': 'ml', 'rnl': 'ml',
    '1iter': 'liter', 'llter': 'liter', 'litre': 'liter',
    'abv': 'abv', 'a8v': 'abv', 'abvv': 'abv',
    'pr00f': 'proof', 'prooof': 'proof', 'pro0f': 'proof',
    'p1nt': 'pint', 'p1n1': 'pint',
    
    # === GOVERNMENT WARNING TEXT ===
    # Common word errors
    '1o': 'to', 'lo': 'to', 't0': 'to',
    '1he': 'the', 'tne': 'the', 'th3': 'the', 'tha': 'the',
    'genera1': 'general', 'generai': 'general', 'gen3ral': 'general',
    'surgeqn': 'surgeon', 'surge0n': 'surgeon', 'surgean': 'surgeon',
    'pregnanacy': 'pregnancy', 'pregnacy': 'pregnancy', 'pregnncy': 'pregnancy',
    'pregnanc': 'pregnancy', 'pregancy': 'pregnancy',
    'defecis': 'defects', 'defecl': 'defects', 'def3cts': 'defects',
    'defeccts': 'defects', 'defets': 'defects',
    'impa1rs': 'impairs', 'impars': 'impairs', 'lmpairs': 'impairs',
    'ab1lity': 'ability', 'abiiity': 'ability', 'abilty': 'ability',
    'hea1th': 'health', 'heaith': 'health', 'h3alth': 'health',
    'prob1ems': 'problems', 'probiems': 'problems', 'problms': 'problems',
    'machlnery': 'machinery', 'mach1nery': 'machinery', 'machinry': 'machinery',
    'operale': 'operate', 'op3rate': 'operate', 'operat3': 'operate',
    'accord1ng': 'according', 'accordlng': 'according', 'accordinq': 'according',
    'shou1d': 'should', 'shouid': 'should', 'shoud': 'should',
    'wom3n': 'women', 'wornen': 'women', 'wamen': 'women',
    'dr1nk': 'drink', 'drlnk': 'drink', 'drnk': 'drink',
    'a1coholic': 'alcoholic', 'aicoholic': 'alcoholic', 'alcoholc': 'alcoholic',
    'alcoho1ic': 'alcoholic', 'aleoholic': 'alcoholic',
    'beverag3s': 'beverages', 'beveraqes': 'beverages', 'bevereges': 'beverages',
    'dur1ng': 'during', 'durinq': 'during', 'durng': 'during',
    'becaus3': 'because', 'b3cause': 'because', 'becuase': 'because',
    'r1sk': 'risk', 'rlsk': 'risk', 'rsk': 'risk',
    'b1rth': 'birth', 'blrth': 'birth', 'brith': 'birth',
    'consumpt1on': 'consumption', 'consumptlon': 'consumption', 'consumpion': 'consumption',
    'dr1ve': 'drive', 'drlve': 'drive', 'driv3': 'drive',
    'caus3': 'cause', 'couse': 'cause',
    'warn1ng': 'warning', 'warnlng': 'warning', 'warninq': 'warning',
    'covernment': 'government', 'governm3nt': 'government', 'qovernment': 'government',
    'g0vernment': 'government',
    
    # === COMMON OCR SUBSTITUTIONS ===
    # Note: 'rn' <-> 'm' corrections are handled specially in apply_ocr_corrections
    # because they need context-aware application
}

# Additional character-level fixes applied after word corrections
CHAR_SUBSTITUTIONS = [
    ('|', 'l'),   # pipe to l
    ('!', 'l'),   # exclamation to l  
    ('$', 's'),   # dollar to s
    ('@', 'a'),   # at to a
]


def apply_ocr_corrections(text, skip_rn_m=False):
    """
    Apply OCR error corrections to text.
    skip_rn_m: Set True for government warning (standard fonts don't need rn<->m fixes)
    """
    if not text:
        return ""
    result = text.lower()
    
    # Apply character substitutions first
    for wrong, correct in CHAR_SUBSTITUTIONS:
        result = result.replace(wrong, correct)
    
    # Apply word corrections
    for wrong, correct in OCR_CORRECTIONS.items():
        result = result.replace(wrong, correct)
    
    # Handle rn <-> m substitutions for brand matching only
    # We try both directions and keep whichever produces a known word
    if not skip_rn_m:
        # Common words where 'm' is correct (OCR might read as 'rn')
        m_words = ['michelob', 'ーmiller', 'beam', 'jameson', 'morgan', 'malibu', 
                   'modelo', 'ーmerlot', 'cream', 'ーmoscato', 'premium', 'ーmalt']
        for word in m_words:
            clean_word = word.replace('ー', '')
            mangled = clean_word.replace('m', 'rn')
            result = result.replace(mangled, clean_word)
    
    return result


def ocr_aware_similarity(s1, s2):
    """Calculate similarity with OCR error awareness."""
    if not s1 or not s2:
        return 0.0
    
    s1_corr = apply_ocr_corrections(s1.lower())
    s2_corr = apply_ocr_corrections(s2.lower())
    
    if s1_corr == s2_corr:
        return 1.0
    
    if s1_corr in s2_corr or s2_corr in s1_corr:
        return 0.95
    
    return SequenceMatcher(None, s1_corr, s2_corr).ratio()


# ============================================================================
# FUZZY MATCHING (OCR-AWARE)
# ============================================================================

def fuzzy_ratio(s1, s2):
    """Calculate similarity ratio (0-100) using OCR-aware matching."""
    return int(ocr_aware_similarity(s1, s2) * 100)


def fuzzy_partial_ratio(s1, s2):
    """Partial matching with OCR correction."""
    if not s1 or not s2:
        return 0
    
    s1_corr = apply_ocr_corrections(s1.lower())
    s2_corr = apply_ocr_corrections(s2.lower())
    
    shorter, longer = (s1_corr, s2_corr) if len(s1_corr) <= len(s2_corr) else (s2_corr, s1_corr)
    
    if shorter in longer:
        return 100
    
    if len(shorter) == 0:
        return 0
    
    # Sliding window
    best_ratio = 0
    for i in range(len(longer) - len(shorter) + 1):
        window = longer[i:i + len(shorter)]
        ratio = SequenceMatcher(None, shorter, window).ratio() * 100
        best_ratio = max(best_ratio, ratio)
    
    return int(best_ratio)


def fuzzy_token_set_ratio(s1, s2):
    """Token-based comparison with OCR awareness."""
    if not s1 or not s2:
        return 0
    
    tokens1 = set(apply_ocr_corrections(s1).split())
    tokens2 = set(apply_ocr_corrections(s2).split())
    
    if not tokens1 or not tokens2:
        return fuzzy_ratio(s1, s2)
    
    intersection = tokens1 & tokens2
    if not intersection:
        return fuzzy_ratio(s1, s2)
    
    return int((len(intersection) / len(tokens1)) * 100)


# ============================================================================
# SINGLE-PASS OCR EXTRACTION
# ============================================================================

def extract_text_from_image(image_path):
    """Single-pass OCR extraction with basic PIL preprocessing."""
    try:
        image = Image.open(image_path)
        
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Light contrast enhancement
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)
        
        # Single OCR pass
        text = pytesseract.image_to_string(image, config='--oem 3 --psm 3')
        
        return text.strip()
        
    except Exception as e:
        return ""


# ============================================================================
# VERIFICATION FUNCTIONS
# ============================================================================

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def normalize_text(text):
    """Normalize text for comparison."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()


def normalize_alcohol_content(text):
    """Extract numeric alcohol percentage from various formats."""
    if not text:
        return ""
    text = text.upper()
    match = re.search(r'(\d+\.?\d*)\s*%', text)
    return match.group(1) if match else text.strip()


def normalize_volume(text):
    """
    Normalize volume text to handle spacing/punctuation variants.
    '12 fl oz' = '12floz' = '12 fl. oz.' = '12FL OZ'
    Returns tuple: (number, unit_normalized)
    """
    if not text:
        return "", ""
    # Lowercase
    t = text.lower()
    # Remove periods
    t = t.replace('.', '')
    # Common OCR fixes
    t = t.replace('o2', 'oz').replace('02', 'oz')
    t = t.replace('f1', 'fl').replace('fi', 'fl')
    
    # Extract number and unit separately
    match = re.match(r'(\d+\.?\d*)\s*(.*)', t.strip())
    if match:
        number = match.group(1)
        unit = match.group(2).replace(' ', '')  # Remove spaces from unit
        return number, unit
    return "", t.replace(' ', '')


def verify_net_contents(input_value, extracted_text):
    """Strict net contents verification - number must match exactly."""
    if not input_value:
        return (True, 100, "Field not provided (optional)")
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    input_num, input_unit = normalize_volume(input_value)
    
    # Find all volume patterns in extracted text
    # Patterns: "12 FL OZ", "750ML", "750 ML", "1.5L", etc.
    volume_patterns = [
        r'(\d+\.?\d*)\s*FL\.?\s*OZ',
        r'(\d+\.?\d*)\s*FLOZ',
        r'(\d+\.?\d*)\s*ML',
        r'(\d+\.?\d*)\s*L\b',
        r'(\d+\.?\d*)\s*LITER',
        r'(\d+\.?\d*)\s*OZ',
    ]
    
    text_upper = extracted_text.upper()
    found_volumes = []
    
    for pattern in volume_patterns:
        matches = re.findall(pattern, text_upper)
        found_volumes.extend(matches)
    
    # Strict number matching
    for found_num in found_volumes:
        try:
            if float(found_num) == float(input_num):
                return (True, 100, f"Exact volume match: {found_num}")
        except ValueError:
            continue
    
    # Also try normalized full string match as fallback
    input_normalized = input_num + input_unit
    text_normalized = normalize_volume(extracted_text)
    text_full = text_normalized[0] + text_normalized[1]
    
    if input_normalized and input_normalized in extracted_text.lower().replace(' ', '').replace('.', ''):
        return (True, 100, "Volume match found")
    
    if found_volumes:
        return (False, 0, f"No match - expected {input_num}, found: {', '.join(set(found_volumes))}")
    return (False, 0, "No volume found in text")


def verify_field(field_value, extracted_text, threshold=70, field_name=None):
    """OCR-aware field verification."""
    if not field_value:
        return (True, 100, "Field not provided (optional)")
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    # Use strict verification for net_contents (numbers must match exactly)
    if field_name == 'net_contents':
        return verify_net_contents(field_value, extracted_text)
    
    field_norm = normalize_text(field_value)
    text_norm = normalize_text(extracted_text)
    
    field_corr = apply_ocr_corrections(field_norm)
    text_corr = apply_ocr_corrections(text_norm)
    
    # Exact match after correction
    if field_corr in text_corr:
        return (True, 100, "Exact match found")
    
    # Partial ratio
    partial_score = fuzzy_partial_ratio(field_norm, text_norm)
    
    # Token set ratio
    token_score = fuzzy_token_set_ratio(field_norm, text_norm)
    
    # Individual word matching (for multi-word fields)
    field_words = [w for w in field_corr.split() if len(w) > 2]
    if field_words:
        word_matches = sum(1 for w in field_words if w in text_corr)
        word_score = int((word_matches / len(field_words)) * 100)
    else:
        word_score = 0
    
    best_score = max(partial_score, token_score, word_score)
    
    if best_score >= threshold:
        return (True, best_score, f"Fuzzy match ({best_score}% similarity)")
    return (False, best_score, f"No match found ({best_score}% similarity)")


def verify_alcohol_content(input_value, extracted_text, threshold=70):
    """Strict alcohol content verification - numbers must match exactly."""
    if not input_value:
        return (True, 100, "Field not provided (optional)")
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    input_norm = normalize_alcohol_content(input_value)
    text_upper = extracted_text.upper()
    text_corrected = apply_ocr_corrections(text_upper.lower()).upper()
    
    patterns = [
        r'ALC\.?\s*/?\s*(\d+\.?\d*)\s*%',
        r'(\d+\.?\d*)\s*%\s*ALC\.?/?VOL\.?',
        r'(\d+\.?\d*)\s*%\s*ABV',
        r'(\d+\.?\d*)\s*%\s*ALC',
        r'(\d+\.?\d*)\s*%\s*BY\s*VOL',
        r'ALCOHOL\s*:?\s*(\d+\.?\d*)\s*%',
        r'(\d+\.?\d*)\s*%\s*ALCOHOL',
        r'(\d+\.?\d*)\s*%',
    ]
    
    found_values = []
    for search_text in [text_upper, text_corrected]:
        for pattern in patterns:
            matches = re.findall(pattern, search_text)
            found_values.extend(matches)
    
    # Strict matching - number must match exactly
    for match in found_values:
        try:
            if float(match) == float(input_norm):
                return (True, 100, f"Exact match: {match}%")
        except ValueError:
            continue
    
    # If no exact match found, report what was found
    if found_values:
        return (False, 0, f"No match - expected {input_norm}%, found: {', '.join(set(found_values))}%")
    return (False, 0, f"No alcohol percentage found in text")


def clean_ocr_noise(text):
    """
    Remove OCR noise/artifacts from text.
    Strips isolated characters, symbols, and short fragments that aren't real words.
    """
    if not text:
        return ""
    
    # Remove common OCR artifacts and symbols
    noise_patterns = [
        r'[=\-]{2,}[>]?',      # ===> or ---
        r'\b[a-z]\d+[a-z]?\b', # m9: or similar
        r'\b\d+[a-z]\b',       # Single letter+number combos like "9)"
        r'[~\|\\<>]{1,}',      # Stray symbols
        r'\b[a-z]{1,2}:',      # Short prefix with colon like "m9:" or "in:"
        r'\s[^\w\s]{1,2}\s',   # Isolated 1-2 char non-word symbols
    ]
    
    result = text
    for pattern in noise_patterns:
        result = re.sub(pattern, ' ', result, flags=re.IGNORECASE)
    
    # Collapse multiple spaces
    result = re.sub(r'\s+', ' ', result)
    
    return result.strip()


def verify_government_warning(extracted_text, threshold=95):
    """
    Government warning verification using keyword detection.
    
    The standard US alcohol warning is always printed in clear, standard fonts.
    No OCR corrections needed - just normalize and check for keywords.
    """
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    # Normalize: lowercase, collapse whitespace
    text = extracted_text.lower()
    text = re.sub(r'\s+', ' ', text)
    
    # Strip ALL non-alphanumeric except spaces (removes ==>, m9:, etc.)
    text_clean = re.sub(r'[^a-z0-9\s]', '', text)
    text_clean = re.sub(r'\s+', ' ', text_clean)
    
    # NO OCR corrections for government warning - it's always standard font
    
    # Key phrases that MUST appear in a valid government warning
    # Using short, robust fragments that survive OCR errors
    required_keywords = [
        'government warning',
        'surgeon general', 
        'pregnan',           # catches pregnancy, pregnant
        'birth defect',
        'consumption',
        'impair',
        'drive',
        'machinery',
        'health problem',
    ]
    
    # Alternative/backup keywords (OCR variants)
    keyword_variants = {
        'government warning': ['covernment warning', 'qovernment warning', 'govemment warning'],
        'surgeon general': ['surgeqn general', 'surgeongeneral', 'surgeon qeneral'],
        'pregnan': ['preqnan', 'preg nan', 'prenant'],
        'birth defect': ['blrth defect', 'birth defecl', 'birthdefect'],
        'consumption': ['consumpt1on', 'consumpti0n'],
        'impair': ['lmpair', '1mpair', 'impalr'],
        'drive': ['dr1ve', 'drlve'],
        'machinery': ['machlnery', 'mach1nery', 'machin'],
        'health problem': ['health prob', 'hea1th problem', 'healthproblem'],
    }
    
    found_keywords = []
    missing_keywords = []
    
    for keyword in required_keywords:
        # Check primary keyword
        if keyword in text_clean:
            found_keywords.append(keyword)
            continue
        
        # Check variants
        variants = keyword_variants.get(keyword, [])
        variant_found = False
        for variant in variants:
            if variant in text_clean:
                found_keywords.append(keyword)
                variant_found = True
                break
        
        if not variant_found:
            missing_keywords.append(keyword)
    
    # Calculate score
    score = int((len(found_keywords) / len(required_keywords)) * 100)
    
    # Pass criteria: must have header + at least 6 of 9 keywords (66%)
    has_header = 'government warning' in found_keywords
    
    if has_header and score >= 66:
        return (True, score, f"Government warning verified ({score}% - {len(found_keywords)}/9 keywords)")
    elif not has_header:
        return (False, score, "GOVERNMENT WARNING header not found")
    else:
        return (False, score, f"Warning incomplete ({score}% - missing: {', '.join(missing_keywords[:3])})")



def verify_label(image_path, label_data):
    """Verify all label fields against extracted text."""
    start_time = time.time()
    
    extracted_text = extract_text_from_image(image_path)
    
    if not extracted_text:
        return {
            'success': False,
            'error': 'Unable to extract text from image',
            'extracted_text': None,
            'fields': {},
            'overall_pass': False,
            'processing_time': time.time() - start_time
        }
    
    results = {
        'success': True,
        'extracted_text': extracted_text,
        'fields': {},
        'overall_pass': True
    }
    
    fields = [
        ('brand_name', label_data.get('brand_name', ''), 90),
        ('class_type', label_data.get('class_type', ''), 80),
        ('net_contents', label_data.get('net_contents', ''), 75),
        ('producer_name', label_data.get('producer_name', ''), 80),
        ('city', label_data.get('city', ''), 70),
        ('country', label_data.get('country', ''), 80),
    ]
    
    for field_name, field_value, threshold in fields:
        is_optional = field_name in ['city', 'country']
        
        if not field_value and is_optional:
            results['fields'][field_name] = {
                'input': field_value,
                'passed': True,
                'score': 100,
                'details': 'Optional field not provided',
                'optional': True
            }
        else:
            passed, score, details = verify_field(field_value, extracted_text, threshold, field_name=field_name)
            results['fields'][field_name] = {
                'input': field_value,
                'passed': passed,
                'score': score,
                'details': details,
                'optional': is_optional
            }
            if not passed and not is_optional:
                results['overall_pass'] = False
    
    # Alcohol content
    alcohol_value = label_data.get('alcohol_content', '')
    if alcohol_value:
        passed, score, details = verify_alcohol_content(alcohol_value, extracted_text, 70)
    else:
        passed, score, details = False, 0, "Required field not provided"
    
    results['fields']['alcohol_content'] = {
        'input': alcohol_value,
        'passed': passed,
        'score': score,
        'details': details,
        'optional': False
    }
    if not passed:
        results['overall_pass'] = False
    
    # Government warning
    passed, score, details = verify_government_warning(extracted_text)
    results['fields']['government_warning'] = {
        'input': 'Required',
        'passed': passed,
        'score': score,
        'details': details,
        'optional': False
    }
    if not passed:
        results['overall_pass'] = False
    
    results['processing_time'] = time.time() - start_time
    
    return results


def format_time(seconds):
    """Format time for display."""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        mins = int(seconds // 60)
        secs = seconds % 60
        return f"{mins}m {secs:.1f}s"


# ============================================================================
# HTML TEMPLATES
# ============================================================================

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alcohol Label Verifier</title>
    <link rel="stylesheet" href="/static/style.css">
    <script src="/static/script.js" defer></script>
</head>
<body>
    <div id="loading-overlay" class="loading-overlay">
        <div class="loading-spinner"></div>
        <div class="loading-text">Processing Images...</div>
        <div class="loading-subtext">This may take a few seconds per image</div>
    </div>
    
    <div class="container">
        <h1>🍷 Alcohol Label Verifier</h1>
        
        <div class="tabs">
            <button class="tab {{ 'active' if active_tab == 'single' else '' }}" onclick="switchTab('single')">Single Upload</button>
            <button class="tab {{ 'active' if active_tab == 'batch' else '' }}" onclick="switchTab('batch')">Batch Upload</button>
        </div>
        
        <div id="single-tab" class="tab-content {{ 'active' if active_tab == 'single' else '' }}">
            <form action="/verify/single" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label>Label Image (PNG/JPG/JPEG)</label>
                    <input type="file" name="image" accept=".png,.jpg,.jpeg" required>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>Brand Name</label>
                        <input type="text" name="brand_name" placeholder="e.g., Silver Oak Ranch" required>
                    </div>
                    <div class="form-group">
                        <label>Class/Type Designation</label>
                        <input type="text" name="class_type" placeholder="e.g., Cabernet Sauvignon" required>
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>Alcohol Content</label>
                        <input type="text" name="alcohol_content" placeholder="e.g., 14.8% (optional for some wines/beers)">
                    </div>
                    <div class="form-group">
                        <label>Net Contents</label>
                        <input type="text" name="net_contents" placeholder="e.g., 750ml" required>
                    </div>
                </div>
                
                <div class="form-row">
                    <div class="form-group">
                        <label>Name of Producer/Bottler</label>
                        <input type="text" name="producer_name" placeholder="e.g., Silver Oak Winery" required>
                    </div>
                    <div class="form-group">
                        <label>City of Bottler/Producer <span class="optional">(optional)</span></label>
                        <input type="text" name="city" placeholder="e.g., Alexander Valley">
                    </div>
                </div>
                
                <div class="form-group">
                    <label>Country of Origin <span class="optional">(optional)</span></label>
                    <input type="text" name="country" placeholder="e.g., USA">
                </div>
                
                <button type="submit">Verify Label</button>
            </form>
            
            {% if single_result %}
            <div class="results">
                {{ render_result(single_result, single_filename) }}
            </div>
            {% endif %}
        </div>
        
        <div id="batch-tab" class="tab-content {{ 'active' if active_tab == 'batch' else '' }}">
            <div class="batch-info">
                <h4>📋 CSV Format Requirements</h4>
                <p>Your CSV file should have the following columns:</p>
                <p><code>image_filename</code>, <code>brand_name</code>, <code>class_type</code>, <code>alcohol_content</code>, <code>net_contents</code>, <code>producer_name</code>, <code>city</code> (optional), <code>country</code> (optional)</p>
                <p style="margin-top: 10px;">Upload the corresponding image files separately below.</p>
            </div>
            
            <form action="/verify/batch" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label>CSV File with Label Data</label>
                    <input type="file" name="csv_file" accept=".csv" required>
                </div>
                
                <div class="form-group">
                    <label>Image Files (select all images referenced in CSV)</label>
                    <input type="file" name="images" accept=".png,.jpg,.jpeg" multiple required>
                </div>
                
                <button type="submit">Verify All Labels</button>
            </form>
            
            {% if batch_results %}
            <div class="results">
                <div class="summary">
                    <div class="summary-card">
                        <div class="summary-number total">{{ batch_results|length }}</div>
                        <div class="summary-label">Total Images</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-number pass">{{ batch_results|selectattr('result.overall_pass')|list|length }}</div>
                        <div class="summary-label">Passed</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-number fail">{{ batch_results|rejectattr('result.overall_pass')|list|length }}</div>
                        <div class="summary-label">Failed</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-number time">{{ total_time }}</div>
                        <div class="summary-label">Total Time</div>
                    </div>
                </div>
                
                {% for item in batch_results %}
                {{ render_result(item.result, item.filename) }}
                {% endfor %}
            </div>
            {% endif %}
        </div>
    </div>
    
    <script>
    function switchTab(tabName) {
        // Hide all tab contents
        document.querySelectorAll('.tab-content').forEach(function(tab) {
            tab.classList.remove('active');
        });
        
        // Remove active from all tab buttons
        document.querySelectorAll('.tab').forEach(function(btn) {
            btn.classList.remove('active');
        });
        
        // Show selected tab content
        document.getElementById(tabName + '-tab').classList.add('active');
        
        // Set active on clicked button (find by text content)
        document.querySelectorAll('.tab').forEach(function(btn) {
            if (tabName === 'single' && btn.textContent.includes('Single')) {
                btn.classList.add('active');
            } else if (tabName === 'batch' && btn.textContent.includes('Batch')) {
                btn.classList.add('active');
            }
        });
    }
    
    function toggleExtracted(id) {
        var el = document.getElementById(id);
        if (el.style.display === 'none') {
            el.style.display = 'block';
        } else {
            el.style.display = 'none';
        }
    }
    </script>
</body>
</html>
"""

RESULT_MACRO = """
{% macro render_result(result, filename) %}
<div class="result-card {{ 'pass' if result.overall_pass else 'fail' }}">
    <div class="result-header">
        <span class="result-title">📄 {{ filename }}</span>
        <div class="result-meta">
            {% if result.processing_time %}
            <span class="processing-time">⏱️ {{ "%.2f"|format(result.processing_time) }}s</span>
            {% endif %}
            <span class="status-badge {{ 'pass' if result.overall_pass else 'fail' }}">
                {{ 'PASSED' if result.overall_pass else 'FAILED' }}
            </span>
        </div>
    </div>
    
    {% if result.error %}
    <p style="color: #ef4444;">{{ result.error }}</p>
    {% else %}
    <div class="field-results">
        {% for field_name, field_data in result.fields.items() %}
        <div class="field-row">
            <span class="field-name">{{ field_name.replace('_', ' ').title() }}</span>
            <span class="field-input">{{ field_data.input or '-' }}</span>
            <span class="field-status {{ 'pass' if field_data.passed else 'fail' }}">
                {{ '✓ Pass' if field_data.passed else '✗ Fail' }}
            </span>
            <span class="field-details">{{ field_data.details }}</span>
        </div>
        {% endfor %}
    </div>
    
    <button class="toggle-text" onclick="toggleExtracted('extracted-{{ filename|replace('.', '-') }}')">
        Toggle Extracted Text
    </button>
    <div id="extracted-{{ filename|replace('.', '-') }}" class="extracted-text" style="display: none;">{{ result.extracted_text }}</div>
    {% endif %}
</div>
{% endmacro %}
"""


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    template = RESULT_MACRO + BASE_TEMPLATE
    return render_template_string(template, single_result=None, batch_results=None, active_tab='single')


@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)


@app.route('/verify/single', methods=['POST'])
def verify_single():
    if 'image' not in request.files:
        return "No image uploaded", 400
    
    file = request.files['image']
    if file.filename == '':
        return "No image selected", 400
    
    if not allowed_file(file.filename):
        return "Invalid file type. Please upload PNG, JPG, or JPEG.", 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
    file.save(filepath)
    
    label_data = {
        'brand_name': request.form.get('brand_name', ''),
        'class_type': request.form.get('class_type', ''),
        'alcohol_content': request.form.get('alcohol_content', ''),
        'net_contents': request.form.get('net_contents', ''),
        'producer_name': request.form.get('producer_name', ''),
        'city': request.form.get('city', ''),
        'country': request.form.get('country', ''),
    }
    
    result = verify_label(filepath, label_data)
    os.remove(filepath)
    
    template = RESULT_MACRO + BASE_TEMPLATE
    return render_template_string(template, single_result=result, single_filename=filename, batch_results=None, active_tab='single')


@app.route('/verify/batch', methods=['POST'])
def verify_batch():
    batch_start_time = time.time()
    
    if 'csv_file' not in request.files:
        return "No CSV file uploaded", 400
    
    csv_file = request.files['csv_file']
    if csv_file.filename == '':
        return "No CSV file selected", 400
    
    if 'images' not in request.files:
        return "No images uploaded", 400
    
    image_files = request.files.getlist('images')
    if not image_files or image_files[0].filename == '':
        return "No images selected", 400
    
    # Save images temporarily
    saved_images = {}
    for img_file in image_files:
        if img_file.filename and allowed_file(img_file.filename):
            filename = secure_filename(img_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
            img_file.save(filepath)
            saved_images[filename] = filepath
    
    # Parse CSV
    try:
        csv_content = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
    except Exception as e:
        return f"Error parsing CSV: {str(e)}", 400
    
    # Process each row
    results = []
    for row in rows:
        image_filename = row.get('image_filename', '').strip()
        
        if not image_filename:
            results.append({
                'filename': 'Unknown',
                'result': {
                    'success': False,
                    'error': 'No image_filename specified in CSV row',
                    'overall_pass': False,
                    'fields': {},
                    'processing_time': 0
                }
            })
            continue
        
        image_path = saved_images.get(image_filename)
        if not image_path:
            results.append({
                'filename': image_filename,
                'result': {
                    'success': False,
                    'error': f'Image file "{image_filename}" not found in uploaded images',
                    'overall_pass': False,
                    'fields': {},
                    'processing_time': 0
                }
            })
            continue
        
        label_data = {
            'brand_name': row.get('brand_name', ''),
            'class_type': row.get('class_type', ''),
            'alcohol_content': row.get('alcohol_content', ''),
            'net_contents': row.get('net_contents', ''),
            'producer_name': row.get('producer_name', ''),
            'city': row.get('city', ''),
            'country': row.get('country', ''),
        }
        
        result = verify_label(image_path, label_data)
        results.append({
            'filename': image_filename,
            'result': result
        })
    
    # Clean up
    for filepath in saved_images.values():
        try:
            os.remove(filepath)
        except:
            pass
    
    total_time = time.time() - batch_start_time
    total_time_str = format_time(total_time)
    
    template = RESULT_MACRO + BASE_TEMPLATE
    return render_template_string(template, single_result=None, batch_results=results, total_time=total_time_str, active_tab='batch')


@app.route('/api/verify', methods=['POST'])
def api_verify():
    """API endpoint for single image verification."""
    if 'image' not in request.files:
        return jsonify({'error': 'No image uploaded'}), 400
    
    file = request.files['image']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': 'Invalid file'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
    file.save(filepath)
    
    if request.content_type and 'application/json' in request.content_type:
        label_data = request.json or {}
    else:
        label_data = {
            'brand_name': request.form.get('brand_name', ''),
            'class_type': request.form.get('class_type', ''),
            'alcohol_content': request.form.get('alcohol_content', ''),
            'net_contents': request.form.get('net_contents', ''),
            'producer_name': request.form.get('producer_name', ''),
            'city': request.form.get('city', ''),
            'country': request.form.get('country', ''),
        }
    
    result = verify_label(filepath, label_data)
    os.remove(filepath)
    
    return jsonify({
        'filename': filename,
        'result': result
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
