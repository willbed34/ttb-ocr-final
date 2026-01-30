"""
Alcohol Label Verifier - IMPROVED VERSION
Context-specific OCR corrections applied per field type.
Enhanced fuzzy matching and robust government warning detection.
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
# CONTEXT-SPECIFIC OCR CORRECTIONS
# ============================================================================

# Character-level substitutions applied first (common OCR errors)
CHAR_SUBSTITUTIONS = {
    '|': 'l',
    '!': 'l',
    '$': 's',
    '@': 'a',
    '0': 'o',  # Context-dependent, applied selectively
    '1': 'l',  # Context-dependent, applied selectively
}

# Brand-specific corrections
BRAND_CORRECTIONS = {
    # Michelob variations
    'mihelob': 'michelob', 'maheleb': 'michelob', 'mabeleb': 'michelob',
    'maheiob': 'michelob', 'mahclob': 'michelob', 'mlchelob': 'michelob',
    'm1chelob': 'michelob', 'miche1ob': 'michelob', 'mictieleb': 'michelob',
    'miibetob': 'michelob', 'cmlicheelob': 'michelob', 'mitehelob': 'michelob',
    'micheleb': 'michelob', 'micheiob': 'michelob', 'michelab': 'michelob',
    'mlcheleb': 'michelob', 'micheloh': 'michelob', 'michclob': 'michelob',
    'micheieb': 'michelob', 'rnichelob': 'michelob', 'miehelob': 'michelob',
    'micheob': 'michelob', 'miheleb': 'michelob',
    # Ultra variations  
    'uttra': 'ultra', 'u1tra': 'ultra', 'uitra': 'ultra', 'ultr4': 'ultra',
    'uiltra': 'ultra', 'uitr4': 'ultra', 'ulira': 'ultra', 'utra': 'ultra',
    # Budweiser variations
    'budwelser': 'budweiser', 'budwe1ser': 'budweiser', 'budwiser': 'budweiser',
    'budwieser': 'budweiser', 'budwelsr': 'budweiser', 'budweisar': 'budweiser',
    'budwaser': 'budweiser', 'budw3iser': 'budweiser',
    # Coors variations
    'c00rs': 'coors', 'co0rs': 'coors', 'coor5': 'coors', 'cooors': 'coors',
    # Miller variations
    'mi11er': 'miller', 'miiler': 'miller', 'm1ller': 'miller', 'mlller': 'miller',
    # Corona variations
    'c0rona': 'corona', 'cor0na': 'corona', 'carona': 'corona', 'corono': 'corona',
    # Heineken variations
    'helneken': 'heineken', 'he1neken': 'heineken', 'hieneken': 'heineken',
    'heiniken': 'heineken', 'heinekn': 'heineken', 'hienken': 'heineken',
    # Stella Artois
    'ste11a': 'stella', 'stelia': 'stella', 'steila': 'stella',
    'art0is': 'artois', 'artols': 'artois', 'artios': 'artois',
    # Modelo
    'mode1o': 'modelo', 'modela': 'modelo', 'm0delo': 'modelo',
    # Guinness
    'gulnness': 'guinness', 'gu1nness': 'guinness', 'guiness': 'guinness',
    'guinnes': 'guinness', 'guinnss': 'guinness', 'guinn3ss': 'guinness',
    # Samuel Adams
    'samue1': 'samuel', 'sarnuel': 'samuel', 'samuei': 'samuel',
    # Pabst
    'pabsi': 'pabst', 'pa8st': 'pabst', 'p4bst': 'pabst',
    # Blue Ribbon
    'b1ue': 'blue', 'biue': 'blue', 'bule': 'blue',
    'rlbbon': 'ribbon', 'r1bbon': 'ribbon', 'ribben': 'ribbon',
    # Natural Light
    'natura1': 'natural', 'naturaal': 'natural', 'naturai': 'natural',
    '1ight': 'light', 'ilght': 'light', 'lighi': 'light', 'l1ght': 'light',
    # Yuengling
    'yueng1ing': 'yuengling', 'yuengllng': 'yuengling', 'yuengiing': 'yuengling',
    # Sierra Nevada
    'slerra': 'sierra', 's1erra': 'sierra', 'siarra': 'sierra', 'sterra': 'sierra',
    'nevado': 'nevada', 'nevad0': 'nevada', 'n3vada': 'nevada',
    # Wine brands
    'baref00t': 'barefoot', 'barefool': 'barefoot', 'barefot': 'barefoot',
    'ye11ow': 'yellow', 'yeilow': 'yellow', 'yel1ow': 'yellow',
    'tal1': 'tail', 'taii': 'tail',
    'suiter': 'sutter', 'suttr': 'sutter', 'suttter': 'sutter',
    'franzla': 'franzia', 'franz1a': 'franzia', 'franza': 'franzia',
    'w00dbridge': 'woodbridge', 'woodbrldge': 'woodbridge', 'woodbridg': 'woodbridge',
    'kenda11': 'kendall', 'kendal1': 'kendall', 'kendaii': 'kendall',
    'jacks0n': 'jackson', 'jckson': 'jackson', 'jacksn': 'jackson',
    'r0bert': 'robert', 'rob3rt': 'robert', 'robart': 'robert',
    'm0ndavi': 'mondavi', 'mondav1': 'mondavi', 'mondavl': 'mondavi',
    'ber1nger': 'beringer', 'beringr': 'beringer', 'beringar': 'beringer',
    'ga11o': 'gallo', 'galio': 'gallo', 'gall0': 'gallo',
    'apoth1c': 'apothic', 'ap0thic': 'apothic', 'apothlc': 'apothic',
    'j0sh': 'josh', 'jash': 'josh',
    'ce11ars': 'cellars', 'cellar5': 'cellars', 'cellrs': 'cellars',
    'cr3ma': 'crema', 'crem4': 'crema',
    'caymu5': 'caymus', 'cayrnus': 'caymus',
    'si1ver': 'silver', 'sliver': 'silver', 's1lver': 'silver',
    '0ak': 'oak', 'oa1k': 'oak',
    '0pus': 'opus', 'opu5': 'opus',
    '0ne': 'one', 'on3': 'one',
    # Spirits brands
    'danie1s': 'daniels', 'danlels': 'daniels', 'danielss': 'daniels', 'dani3ls': 'daniels',
    'j1m': 'jim', 'jlm': 'jim',
    'b3am': 'beam', 'bearn': 'beam',
    'johnn1e': 'johnnie', 'johnnle': 'johnnie',
    'wa1ker': 'walker', 'waker': 'walker', 'walkar': 'walker',
    'cr0wn': 'crown', 'crwn': 'crown', 'crawn': 'crown',
    'roya1': 'royal', 'royai': 'royal', 'rayal': 'royal',
    'james0n': 'jameson', 'jarneson': 'jameson',
    'henness1': 'hennessy', 'hennessey': 'hennessy', 'henesy': 'hennessy',
    'hennssy': 'hennessy', 'hennesey': 'hennessy',
    'gr3y': 'grey', 'groy': 'grey',
    'g00se': 'goose', 'go0se': 'goose', 'gose': 'goose',
    'abso1ut': 'absolut', 'absolui': 'absolut', 'absalut': 'absolut',
    'smlrnoff': 'smirnoff', 'sm1rnoff': 'smirnoff', 'smirnof': 'smirnoff', 'smirn0ff': 'smirnoff',
    'tit0s': 'titos', 'tltos': 'titos',
    'patr0n': 'patron', 'pairon': 'patron', 'patrn': 'patron',
    'd0n': 'don', 'dan': 'don',
    'ju1io': 'julio', 'jull0': 'julio', 'juli0': 'julio',
    'casamig0s': 'casamigos', 'casarnigos': 'casamigos', 'casamgos': 'casamigos',
    'capta1n': 'captain', 'captian': 'captain', 'captln': 'captain',
    'm0rgan': 'morgan', 'margan': 'morgan', 'morgn': 'morgan',
    'bacardl': 'bacardi', 'bacard1': 'bacardi', 'barcadi': 'bacardi',
    'ma1ibu': 'malibu', 'mallbu': 'malibu', 'mal1bu': 'malibu',
    # Producers
    'anhueser': 'anheuser', 'anheusur': 'anheuser', 'anheuer': 'anheuser',
    'anheuser-busck': 'anheuser-busch', 'anheuser-bush': 'anheuser-busch',
    'busch': 'busch', 'busck': 'busch', 'bu5ch': 'busch',
    'mi11ercoors': 'millercoors', 'millercoor5': 'millercoors',
    'diage0': 'diageo', 'd1ageo': 'diageo', 'diagao': 'diageo',
    'conste11ation': 'constellation', 'constelation': 'constellation',
    'pern0d': 'pernod', 'pernad': 'pernod',
    'r1card': 'ricard', 'rlcard': 'ricard',
    'br0wn': 'brown', 'brwn': 'brown',
    'f0rman': 'forman', 'forrnan': 'forman',
}

# Wine/beer type corrections
TYPE_CORRECTIONS = {
    # Beer types
    '1ager': 'lager', 'iager': 'lager', 'lag3r': 'lager', 'lagr': 'lager',
    'pi1sner': 'pilsner', 'pilsnar': 'pilsner', 'plisner': 'pilsner',
    'a1e': 'ale', 'aie': 'ale',
    '1pa': 'ipa', 'lpa': 'ipa',
    'st0ut': 'stout', 'siout': 'stout', 'stoui': 'stout',
    'p0rter': 'porter', 'portr': 'porter', 'porier': 'porter',
    'wh3at': 'wheat', 'wheal': 'wheat',
    'go1d': 'gold', 'g0ld': 'gold', 'goid': 'gold', 'goll': 'gold',
    'pu re': 'pure', 'pue': 'pure', 'puré': 'pure',
    # Wine types
    'cabern3t': 'cabernet', 'cabernei': 'cabernet', 'cabarnet': 'cabernet', 'cabernett': 'cabernet',
    'sauvlgnon': 'sauvignon', 'sauvign0n': 'sauvignon', 'sauvignan': 'sauvignon', 'sauv1gnon': 'sauvignon',
    'chardonn4y': 'chardonnay', 'chardannay': 'chardonnay', 'chardonay': 'chardonnay', 'chardonnav': 'chardonnay',
    'pin0t': 'pinot', 'plnot': 'pinot', 'pnot': 'pinot',
    'n0ir': 'noir', 'nolr': 'noir',
    'grig1o': 'grigio', 'grlgio': 'grigio', 'grigl0': 'grigio',
    'merl0t': 'merlot', 'merloi': 'merlot', 'meriot': 'merlot',
    'r1esling': 'riesling', 'riesiing': 'riesling', 'riesllng': 'riesling',
    'moscat0': 'moscato', 'mascato': 'moscato', 'moscoto': 'moscato',
    'z1nfandel': 'zinfandel', 'zinfande1': 'zinfandel', 'zlnfandel': 'zinfandel',
    'ma1bec': 'malbec', 'malbac': 'malbec', 'maibec': 'malbec',
    # Spirit types
    'bourb0n': 'bourbon', 'bourban': 'bourbon', 'bourbn': 'bourbon',
    'wh1skey': 'whiskey', 'whlskey': 'whiskey', 'whisk3y': 'whiskey',
    'wh1sky': 'whisky', 'whlsky': 'whisky', 'whisk3': 'whisky',
    'v0dka': 'vodka', 'vodko': 'vodka', 'vdka': 'vodka',
    'tequ1la': 'tequila', 'tequlia': 'tequila', 'teqila': 'tequila',
    'rurn': 'rum',
    'g1n': 'gin', 'gln': 'gin',
    'br4ndy': 'brandy', 'brandv': 'brandy',
    'c0gnac': 'cognac', 'cagnac': 'cognac', 'cognc': 'cognac',
    # Common descriptors
    'californ1a': 'california', 'calfornia': 'california', 'californla': 'california',
    'sing1e': 'single', 'slngle': 'single',
    'barre1': 'barrel', 'barr3l': 'barrel',
    'stra1ght': 'straight', 'stralght': 'straight',
    'organ1c': 'organic', 'organlc': 'organic',
}

# Volume-specific corrections
VOLUME_CORRECTIONS = {
    # oz variations
    'o2': 'oz', '02': 'oz', 'o7': 'oz', '07': 'oz', '0z': 'oz',
    'oZ': 'oz', 'Oz': 'oz', 'OZ': 'oz',
    # fl variations
    'f1': 'fl', 'fi': 'fl', 'fL': 'fl', 'FL': 'fl', 'Fl': 'fl',
    # ml variations
    'm1': 'ml', 'mi': 'ml', 'rnl': 'ml', 'mL': 'ml', 'ML': 'ml', 'Ml': 'ml',
    # liter variations
    '1iter': 'liter', 'llter': 'liter', 'litre': 'liter', 'l1ter': 'liter',
    # pint
    'p1nt': 'pint', 'p1n1': 'pint', 'plnt': 'pint',
}

# Alcohol content specific corrections
ALCOHOL_CORRECTIONS = {
    'a1c': 'alc', 'aic': 'alc', 'alcc': 'alc', 'aLc': 'alc',
    'ALC': 'alc', 'ALc': 'alc', 'Alc': 'alc',
    'alg': 'alc',  # Common OCR error
    'vo1': 'vol', 'voi': 'vol', 'v0l': 'vol', 'VOL': 'vol', 'Vol': 'vol',
    'voll': 'vol', 'voL': 'vol',
    'abv': 'abv', 'a8v': 'abv', 'abvv': 'abv', 'ABV': 'abv',
    'pr00f': 'proof', 'prooof': 'proof', 'pro0f': 'proof',
    'dl': 'vol',  # "ALC DL" -> "ALC VOL" 
}


def apply_corrections(text, corrections_dict):
    """Apply a dictionary of corrections to text."""
    if not text:
        return ""
    result = text.lower()
    for wrong, correct in corrections_dict.items():
        result = result.replace(wrong.lower(), correct)
    return result


def apply_brand_corrections(text):
    """Apply brand-specific OCR corrections."""
    result = apply_corrections(text, BRAND_CORRECTIONS)
    # Handle rn -> m substitution for brand names
    rn_to_m_words = ['michelob', 'miller', 'beam', 'jameson', 'morgan', 'malibu', 
                     'modelo', 'merlot', 'cream', 'moscato', 'premium', 'malt',
                     'forman', 'mendocino']
    for word in rn_to_m_words:
        mangled = word.replace('m', 'rn')
        result = result.replace(mangled, word)
    return result


def apply_type_corrections(text):
    """Apply wine/beer type-specific OCR corrections."""
    return apply_corrections(text, TYPE_CORRECTIONS)


def apply_volume_corrections(text):
    """Apply volume-specific OCR corrections."""
    result = text
    # Case-insensitive replacement
    for wrong, correct in VOLUME_CORRECTIONS.items():
        pattern = re.compile(re.escape(wrong), re.IGNORECASE)
        result = pattern.sub(correct, result)
    return result


def apply_alcohol_corrections(text):
    """Apply alcohol content-specific OCR corrections."""
    result = text
    for wrong, correct in ALCOHOL_CORRECTIONS.items():
        pattern = re.compile(re.escape(wrong), re.IGNORECASE)
        result = pattern.sub(correct, result)
    return result


# ============================================================================
# FUZZY MATCHING UTILITIES
# ============================================================================

def fuzzy_ratio(s1, s2):
    """Calculate similarity ratio (0-100)."""
    if not s1 or not s2:
        return 0
    return int(SequenceMatcher(None, s1.lower(), s2.lower()).ratio() * 100)


def fuzzy_partial_ratio(s1, s2):
    """Partial matching - check if shorter string is contained in longer."""
    if not s1 or not s2:
        return 0
    
    s1_lower = s1.lower()
    s2_lower = s2.lower()
    
    shorter, longer = (s1_lower, s2_lower) if len(s1_lower) <= len(s2_lower) else (s2_lower, s1_lower)
    
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
    """Token-based comparison."""
    if not s1 or not s2:
        return 0
    
    tokens1 = set(s1.lower().split())
    tokens2 = set(s2.lower().split())
    
    if not tokens1 or not tokens2:
        return fuzzy_ratio(s1, s2)
    
    intersection = tokens1 & tokens2
    if not intersection:
        return fuzzy_ratio(s1, s2)
    
    return int((len(intersection) / len(tokens1)) * 100)


def word_match_score(field_words, text):
    """Calculate what percentage of field words appear in text."""
    if not field_words:
        return 0
    text_lower = text.lower()
    matches = sum(1 for w in field_words if w.lower() in text_lower)
    return int((matches / len(field_words)) * 100)


# ============================================================================
# OCR EXTRACTION
# ============================================================================

def extract_text_from_image(image_path):
    """
    Multi-strategy OCR extraction.
    Uses multiple preprocessing approaches and combines results to maximize text capture.
    Different preprocessing works better for different parts of labels (light text, dark text, etc.)
    """
    try:
        image = Image.open(image_path)
        
        all_texts = []
        
        # Strategy 1: Basic grayscale + moderate contrast (good general purpose)
        img1 = image.convert('L')
        img1 = ImageEnhance.Contrast(img1).enhance(1.5)
        text1 = pytesseract.image_to_string(img1, config='--oem 3 --psm 3')
        all_texts.append(text1)
        
        # Strategy 2: High contrast (captures faint text better)
        img2 = image.convert('L')
        img2 = ImageEnhance.Contrast(img2).enhance(2.0)
        text2 = pytesseract.image_to_string(img2, config='--oem 3 --psm 3')
        all_texts.append(text2)
        
        # Strategy 3: Sharpen + contrast (captures stylized/script fonts better)
        img3 = image.convert('L')
        img3 = img3.filter(ImageFilter.SHARPEN)
        img3 = ImageEnhance.Contrast(img3).enhance(1.5)
        text3 = pytesseract.image_to_string(img3, config='--oem 3 --psm 3')
        all_texts.append(text3)
        
        # Strategy 4: Threshold/binarize (clean separation for printed text)
        img4 = image.convert('L')
        img4 = img4.point(lambda x: 0 if x < 128 else 255, '1')
        text4 = pytesseract.image_to_string(img4, config='--oem 3 --psm 3')
        all_texts.append(text4)
        
        # Combine all extracted text (deduplicate words while preserving order)
        combined = " ".join(all_texts)
        combined = " ".join(combined.split())  # Normalize whitespace
        
        return combined
        
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


def verify_brand_name(input_value, extracted_text, threshold=80):
    """Verify brand name with brand-specific OCR corrections."""
    if not input_value:
        return (True, 100, "Field not provided (optional)")
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    input_norm = normalize_text(input_value)
    text_norm = normalize_text(extracted_text)
    
    # Apply brand-specific corrections to both
    input_corr = apply_brand_corrections(input_norm)
    text_corr = apply_brand_corrections(text_norm)
    
    # Exact match after correction
    if input_corr in text_corr:
        return (True, 100, "Exact match found")
    
    # Try matching individual words (for multi-word brands)
    input_words = [w for w in input_corr.split() if len(w) > 1]
    if input_words:
        word_score = word_match_score(input_words, text_corr)
        if word_score >= 100:
            return (True, 100, "All brand words found")
        if word_score >= threshold:
            return (True, word_score, f"Brand match ({word_score}% words found)")
    
    # Fuzzy matching
    partial_score = fuzzy_partial_ratio(input_corr, text_corr)
    if partial_score >= threshold:
        return (True, partial_score, f"Fuzzy match ({partial_score}% similarity)")
    
    return (False, partial_score, f"Brand not found ({partial_score}% similarity)")


def verify_class_type(input_value, extracted_text, threshold=75):
    """Verify class/type designation with type-specific OCR corrections."""
    if not input_value:
        return (True, 100, "Field not provided (optional)")
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    input_norm = normalize_text(input_value)
    text_norm = normalize_text(extracted_text)
    
    # Apply type-specific corrections
    input_corr = apply_type_corrections(input_norm)
    text_corr = apply_type_corrections(text_norm)
    
    # Exact match
    if input_corr in text_corr:
        return (True, 100, "Exact match found")
    
    # Word matching (important for multi-word types like "California Cabernet Sauvignon")
    input_words = [w for w in input_corr.split() if len(w) > 2]
    if input_words:
        word_score = word_match_score(input_words, text_corr)
        if word_score >= 100:
            return (True, 100, "All type words found")
        if word_score >= threshold:
            return (True, word_score, f"Type match ({word_score}% words found)")
    
    # Fuzzy matching
    partial_score = fuzzy_partial_ratio(input_corr, text_corr)
    token_score = fuzzy_token_set_ratio(input_corr, text_corr)
    best_score = max(partial_score, token_score)
    
    if best_score >= threshold:
        return (True, best_score, f"Fuzzy match ({best_score}% similarity)")
    
    return (False, best_score, f"Type not found ({best_score}% similarity)")


def verify_net_contents(input_value, extracted_text):
    """Strict net contents verification - number must match exactly."""
    if not input_value:
        return (True, 100, "Field not provided (optional)")
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    # Apply volume-specific corrections
    text_corr = apply_volume_corrections(extracted_text)
    input_corr = apply_volume_corrections(input_value)
    
    # Extract number from input
    input_match = re.search(r'(\d+\.?\d*)', input_corr)
    if not input_match:
        return (False, 0, "Could not parse input volume")
    input_num = input_match.group(1)
    
    # Find all volume patterns in corrected text
    volume_patterns = [
        r'(\d+\.?\d*)\s*fl\.?\s*oz',
        r'(\d+\.?\d*)\s*floz',
        r'(\d+\.?\d*)\s*ml',
        r'(\d+\.?\d*)\s*l\b',
        r'(\d+\.?\d*)\s*liter',
        r'(\d+\.?\d*)\s*oz',
        r'(\d+\.?\d*)\s*pint',
    ]
    
    text_lower = text_corr.lower()
    found_volumes = []
    
    for pattern in volume_patterns:
        matches = re.findall(pattern, text_lower)
        found_volumes.extend(matches)
    
    # Strict number matching
    for found_num in found_volumes:
        try:
            if float(found_num) == float(input_num):
                return (True, 100, f"Exact volume match: {found_num}")
        except ValueError:
            continue
    
    if found_volumes:
        return (False, 0, f"No match - expected {input_num}, found: {', '.join(set(found_volumes))}")
    return (False, 0, "No volume found in text")


def verify_alcohol_content(input_value, extracted_text):
    """Strict alcohol content verification - numbers must match exactly."""
    if not input_value:
        return (True, 100, "Field not provided (optional)")
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    # Apply alcohol-specific corrections
    text_corr = apply_alcohol_corrections(extracted_text)
    
    # Extract number from input
    input_match = re.search(r'(\d+\.?\d*)', input_value)
    if not input_match:
        return (False, 0, "Could not parse input alcohol content")
    input_num = input_match.group(1)
    
    # Find all alcohol percentage patterns in corrected text  
    text_lower = text_corr.lower()
    
    patterns = [
        r'(\d+\.?\d*)\s*%\s*alc',
        r'(\d+\.?\d*)\s*%\s*vol',
        r'(\d+\.?\d*)\s*%\s*abv',
        r'alc\.?/?vol\.?\s*(\d+\.?\d*)\s*%',
        r'alc\.?\s*/?\s*(\d+\.?\d*)\s*%',
        r'(\d+\.?\d*)\s*%\s*by\s*vol',
        r'alcohol\s*:?\s*(\d+\.?\d*)\s*%',
        r'(\d+\.?\d*)\s*%\s*alcohol',
        r'(\d+\.?\d*)\s*alc/vol',
        r'(\d+\.?\d*)\s*alc\s*/\s*vol',
    ]
    
    found_values = set()
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        found_values.update(matches)
    
    # Also look for standalone percentages near "alc" or "vol"
    # Split text into segments and look for numbers near alcohol indicators
    if not found_values:
        # Find all percentages
        all_percents = re.findall(r'(\d+\.?\d*)\s*%', text_lower)
        # Check if "alc" or "vol" appears in text
        if 'alc' in text_lower or 'vol' in text_lower:
            found_values.update(all_percents)
    
    # Strict matching - number must match exactly
    for match in found_values:
        try:
            if float(match) == float(input_num):
                return (True, 100, f"Exact match: {match}%")
        except ValueError:
            continue
    
    if found_values:
        return (False, 0, f"No match - expected {input_num}%, found: {', '.join(found_values)}%")
    return (False, 0, "No alcohol percentage found in text")


def verify_producer_name(input_value, extracted_text, threshold=75):
    """Verify producer/bottler name with brand corrections."""
    if not input_value:
        return (True, 100, "Field not provided (optional)")
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    input_norm = normalize_text(input_value)
    text_norm = normalize_text(extracted_text)
    
    # Apply brand corrections (producers often share naming patterns with brands)
    input_corr = apply_brand_corrections(input_norm)
    text_corr = apply_brand_corrections(text_norm)
    
    # Exact match
    if input_corr in text_corr:
        return (True, 100, "Exact match found")
    
    # Word matching
    input_words = [w for w in input_corr.split() if len(w) > 2]
    if input_words:
        word_score = word_match_score(input_words, text_corr)
        if word_score >= 100:
            return (True, 100, "All producer words found")
        if word_score >= threshold:
            return (True, word_score, f"Producer match ({word_score}% words found)")
    
    # Fuzzy matching
    partial_score = fuzzy_partial_ratio(input_corr, text_corr)
    if partial_score >= threshold:
        return (True, partial_score, f"Fuzzy match ({partial_score}% similarity)")
    
    return (False, partial_score, f"Producer not found ({partial_score}% similarity)")


def verify_location(input_value, extracted_text, field_name, threshold=70):
    """Verify city or country with basic matching."""
    if not input_value:
        return (True, 100, "Optional field not provided")
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    input_norm = normalize_text(input_value)
    text_norm = normalize_text(extracted_text)
    
    # Exact match
    if input_norm in text_norm:
        return (True, 100, "Exact match found")
    
    # Fuzzy match
    partial_score = fuzzy_partial_ratio(input_norm, text_norm)
    if partial_score >= threshold:
        return (True, partial_score, f"Match found ({partial_score}% similarity)")
    
    return (False, partial_score, f"{field_name.title()} not found ({partial_score}% similarity)")


def verify_government_warning(extracted_text, threshold=66):
    """
    Government warning verification using keyword detection.
    
    Labels sometimes have OCR issues like (2) appearing twice instead of (1)/(2),
    or missing punctuation. We verify based on required keywords.
    """
    if not extracted_text:
        return (False, 0, "No text extracted from image")
    
    # Normalize: lowercase, collapse whitespace, remove most punctuation
    text = extracted_text.lower()
    text = re.sub(r'\s+', ' ', text)
    
    # Strip non-alphanumeric except spaces
    text_clean = re.sub(r'[^a-z0-9\s]', '', text)
    text_clean = re.sub(r'\s+', ' ', text_clean)
    
    # Required keywords/phrases that must appear
    required_keywords = [
        'government warning',
        'surgeon general', 
        'women',
        'drink',
        'alcoholic beverages',
        'pregnancy',
        'birth defect',
        'consumption',
        'impair',
        'ability',
        'drive',
        'machinery',
        'health problem',
    ]
    
    # Alternative spellings/OCR variants
    keyword_variants = {
        'government warning': ['covernment warning', 'qovernment warning', 'govemment warning', 'governmentwarning'],
        'surgeon general': ['surgeqn general', 'surgeongeneral', 'surgeon qeneral', 'surgeongenera', 'surgeon genera'],
        'women': ['wornen', 'wom3n', 'wamen'],
        'drink': ['drlnk', 'dr1nk', 'drnk'],
        'alcoholic beverages': ['alcoholic beverag', 'alcoholicbeverages', 'aleoholic beverages'],
        'pregnancy': ['pregnan', 'preg nan', 'prenant', 'pregnacy'],
        'birth defect': ['blrth defect', 'birth defecl', 'birthdefect', 'birth detect'],
        'consumption': ['consumpt1on', 'consumpti0n', 'consumpton'],
        'impair': ['lmpair', '1mpair', 'impalr'],
        'ability': ['ab1lity', 'abiiity', 'abilty'],
        'drive': ['dr1ve', 'drlve', 'driv3'],
        'machinery': ['machlnery', 'mach1nery', 'machin', 'machnery'],
        'health problem': ['health prob', 'hea1th problem', 'healthproblem', 'health problems'],
    }
    
    found_keywords = []
    missing_keywords = []
    
    for keyword in required_keywords:
        # Check primary keyword
        if keyword.replace(' ', '') in text_clean.replace(' ', ''):
            found_keywords.append(keyword)
            continue
        if keyword in text_clean:
            found_keywords.append(keyword)
            continue
        
        # Check variants
        variants = keyword_variants.get(keyword, [])
        variant_found = False
        for variant in variants:
            if variant.replace(' ', '') in text_clean.replace(' ', ''):
                found_keywords.append(keyword)
                variant_found = True
                break
        
        if not variant_found:
            missing_keywords.append(keyword)
    
    # Calculate score
    score = int((len(found_keywords) / len(required_keywords)) * 100)
    
    # Pass criteria: must have header + at least threshold% of keywords
    has_header = 'government warning' in found_keywords
    
    if has_header and score >= threshold:
        return (True, score, f"Government warning verified ({len(found_keywords)}/{len(required_keywords)} keywords)")
    elif not has_header:
        return (False, score, "GOVERNMENT WARNING header not found")
    else:
        return (False, score, f"Warning incomplete ({score}% - missing: {', '.join(missing_keywords[:3])}...)")


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
    
    # Brand name
    passed, score, details = verify_brand_name(
        label_data.get('brand_name', ''), extracted_text
    )
    results['fields']['brand_name'] = {
        'input': label_data.get('brand_name', ''),
        'passed': passed,
        'score': score,
        'details': details,
        'optional': False
    }
    if not passed:
        results['overall_pass'] = False
    
    # Class/Type
    passed, score, details = verify_class_type(
        label_data.get('class_type', ''), extracted_text
    )
    results['fields']['class_type'] = {
        'input': label_data.get('class_type', ''),
        'passed': passed,
        'score': score,
        'details': details,
        'optional': False
    }
    if not passed:
        results['overall_pass'] = False
    
    # Net Contents
    passed, score, details = verify_net_contents(
        label_data.get('net_contents', ''), extracted_text
    )
    results['fields']['net_contents'] = {
        'input': label_data.get('net_contents', ''),
        'passed': passed,
        'score': score,
        'details': details,
        'optional': False
    }
    if not passed:
        results['overall_pass'] = False
    
    # Producer Name
    passed, score, details = verify_producer_name(
        label_data.get('producer_name', ''), extracted_text
    )
    results['fields']['producer_name'] = {
        'input': label_data.get('producer_name', ''),
        'passed': passed,
        'score': score,
        'details': details,
        'optional': False
    }
    if not passed:
        results['overall_pass'] = False
    
    # City (optional)
    city_value = label_data.get('city', '')
    if city_value:
        passed, score, details = verify_location(city_value, extracted_text, 'city')
    else:
        passed, score, details = True, 100, "Optional field not provided"
    results['fields']['city'] = {
        'input': city_value,
        'passed': passed,
        'score': score,
        'details': details,
        'optional': True
    }
    
    # Country (optional)
    country_value = label_data.get('country', '')
    if country_value:
        passed, score, details = verify_location(country_value, extracted_text, 'country')
    else:
        passed, score, details = True, 100, "Optional field not provided"
    results['fields']['country'] = {
        'input': country_value,
        'passed': passed,
        'score': score,
        'details': details,
        'optional': True
    }
    
    # Alcohol content
    alcohol_value = label_data.get('alcohol_content', '')
    if alcohol_value:
        passed, score, details = verify_alcohol_content(alcohol_value, extracted_text)
    else:
        passed, score, details = True, 100, "Field not provided (optional)"
    
    results['fields']['alcohol_content'] = {
        'input': alcohol_value,
        'passed': passed,
        'score': score,
        'details': details,
        'optional': not bool(alcohol_value)  # Required if provided
    }
    if alcohol_value and not passed:
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
                        <label>Alcohol Content <span class="optional">(optional)</span></label>
                        <input type="text" name="alcohol_content" placeholder="e.g., 14.8%">
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
        document.querySelectorAll('.tab-content').forEach(function(tab) {
            tab.classList.remove('active');
        });
        document.querySelectorAll('.tab').forEach(function(btn) {
            btn.classList.remove('active');
        });
        document.getElementById(tabName + '-tab').classList.add('active');
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
    
    saved_images = {}
    for img_file in image_files:
        if img_file.filename and allowed_file(img_file.filename):
            filename = secure_filename(img_file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}_{filename}")
            img_file.save(filepath)
            saved_images[filename] = filepath
    
    try:
        csv_content = csv_file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
    except Exception as e:
        return f"Error parsing CSV: {str(e)}", 400
    
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
