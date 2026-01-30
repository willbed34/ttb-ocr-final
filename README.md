# Alcohol Label Verifier

An AI-assisted Flask web application that verifies alcohol beverage label information against uploaded images using OCR and OCR-aware fuzzy matching.

This project is a **standalone proof-of-concept** built in response to the provided take-home instructions and stakeholder requirements. Its purpose is to reduce manual effort in routine alcohol label compliance checks while **preserving human oversight and final decision-making**.

---

## Deployed Prototype

**Live Application:** https://best-prompt.onrender.com/

**How to Use:**
1. Visit the deployed URL to test the working prototype, **or**
2. Download the source code and run locally for faster performance

> **Performance Note:**  
> The deployed version runs on Render's free tier, which introduces cold starts and limited compute. Processing time may exceed the ~5-second target on first requests. Local execution is significantly faster.

---

## Stakeholder Requirements Addressed

This prototype was designed to address specific concerns raised during stakeholder interviews:

| Stakeholder | Concern | Solution |
|-------------|---------|----------|
| **Sarah Chen** (Deputy Director) | Processing must complete in ~5 seconds or agents won't use it | Local Tesseract OCR eliminates API latency; single-pass processing; image resizing for large uploads |
| **Sarah Chen** | Interface must be simple enough for her 73-year-old mother | Clean two-tab interface with obvious buttons; no hidden menus or complex navigation |
| **Sarah Chen** | Batch upload support (Janet's request) | CSV + multi-image upload processes entire batches in one operation |
| **Marcus Williams** (IT Admin) | Firewall blocks external API endpoints | Fully offline OCR processing—no external network calls required |
| **Marcus Williams** | Standalone proof-of-concept (no COLA integration) | Self-contained Flask app with no external dependencies beyond Tesseract |
| **Dave Morrison** (Senior Agent) | Case differences shouldn't cause false failures ("STONE'S THROW" vs "Stone's Throw") | Case-insensitive fuzzy matching with OCR error tolerance |
| **Dave Morrison** | Nuance and judgment still required | Tool provides pass/fail + confidence scores; final decision remains with agent |
| **Jenny Park** (Junior Agent) | Government warning must be exact—word-for-word, proper formatting | Strict keyword detection requiring 8/9 key phrases (89%); header must be present |
| **Jenny Park** | Handle imperfect images (angles, glare, lighting) | Preprocessing with contrast enhancement; large image resizing; graceful degradation |

---

## Technical Approach

### Architecture Decision: Local OCR vs. Cloud APIs

We evaluated cloud vision APIs (Google Vision, AWS Textract, Azure Computer Vision) against local Tesseract OCR and chose local processing because:

1. **Speed:** Eliminates 200-500ms network round-trip per image
2. **Reliability:** No firewall/proxy issues (per Marcus's feedback about the failed scanning vendor pilot)
3. **Cost:** No per-request API charges for a proof-of-concept
4. **Privacy:** Label images never leave the server
5. **Simplicity:** Single Docker container with no external service dependencies

### Matching Strategy

- **Fuzzy string matching** with OCR error correction dictionary (200+ common OCR misreads)
- **Strict numeric matching** for ABV and volume (no fuzzy tolerance—numbers must match exactly)
- **Keyword-based government warning detection** requiring 8/9 key phrases plus header

### Performance Optimizations

- Compiled regex pattern for OCR corrections (single-pass vs. 200+ sequential replacements)
- Pre-corrected text reused across all field validations (eliminates redundant processing)
- Image resizing for uploads >2000px (common with phone photos)
- Single Tesseract pass with optimized PSM mode

---

## Verification Fields & Thresholds

Thresholds were calibrated through trial-and-error testing on real and synthetic labels, balancing OCR noise against false positives from stylized branding.

| Field | Required | Threshold | Rationale |
|-------|----------|-----------|-----------|
| Brand Name | Yes | 70% | Allow for stylized/decorative fonts |
| Class/Type | Yes | 80% | More standardized text |
| Net Contents | Yes | Exact numeric | Numbers must match precisely |
| Producer/Bottler | Yes | 80% | Usually in cleaner fonts |
| City | No | 70% | Optional, more lenient |
| Country | No | 80% | Standard country names |
| Alcohol Content | Yes | Exact numeric | Numbers must match precisely |
| Government Warning | Yes | 89% (8/9 keywords) | Per Jenny's strictness requirement |

---

## Government Warning Validation

The application verifies the required U.S. alcohol warning using **keyword-based detection** rather than brittle full-string matching. This approach tolerates minor OCR artifacts while remaining strict about required content.

**Required elements (must find 8 of 9):**
- `GOVERNMENT WARNING` (header—mandatory)
- `surgeon general`
- `pregnan` (catches pregnancy/pregnant)
- `birth defect`
- `consumption`
- `impair`
- `drive`
- `machinery`
- `health problem`

Labels missing the `GOVERNMENT WARNING` header automatically fail regardless of other content.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Tesseract OCR installed and on PATH

### Local Installation

```bash
# Clone repository
git clone <repository-url>
cd alcohol-label-verifier

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

Visit `http://localhost:5000` in your browser.

### Docker Deployment

```bash
docker build -t alcohol-label-verifier .
docker run -p 5000:5000 alcohol-label-verifier
```

---

## Usage

### Single Label Verification

1. Click the **Single Upload** tab
2. Upload a label image (PNG, JPG, or JPEG)
3. Fill in the label data fields
4. Click **Verify Label**
5. Review field-by-field results

### Batch Verification

1. Click the **Batch Upload** tab
2. Prepare a CSV file with columns:
   - `image_filename`, `brand_name`, `class_type`, `alcohol_content`, `net_contents`, `producer_name`, `city` (optional), `country` (optional)
3. Upload the CSV and all referenced image files
4. Click **Verify All Labels**
5. Review summary statistics and per-label results

### API Endpoint

```bash
curl -X POST http://localhost:5000/api/verify \
  -F "image=@label.png" \
  -F "brand_name=Silver Oak Ranch" \
  -F "class_type=Cabernet Sauvignon" \
  -F "alcohol_content=14.8%" \
  -F "net_contents=750ml" \
  -F "producer_name=Silver Oak Winery"
```

---

## Project Structure

```
alcohol-label-verifier/
├── app.py              # Main Flask application
├── Dockerfile          # Container configuration
├── requirements.txt    # Python dependencies
├── render.yaml         # Render deployment config
├── static/
│   ├── style.css       # UI styles
│   └── script.js       # Client-side JavaScript
├── test_data           # Folder containing test images and csv for batch upload
└── README.md           # This file
```

---

## Testing

I've tested this application extensively against real and AI-generated images. 
While not always 100% accurate, it does fare decently well, and OCR failures can indicate bad readibility on the label.
In the test_data folder, you'll see AI generated images as well as a real alcohol label.
The AI generated images contain both correct and incorrect labels. The real label is correct.
Feel free to use these files to test against my app. Please do not load all ten at once, as I am limited by Render's free subscription space allocations.


---

## Known Limitations

This is a prototype with intentional scope boundaries:

| Limitation | Rationale |
|------------|-----------|
| **Processing Timing** | I am using Render's free subscription, so there is more latency due to these basic servers |
| **Space allocation** | Render's free subscription doesn't provide the user with much space, so the app will be overloaded with mass upload |
| **Not adversarially robust** | A sophisticated applicant could potentially obfuscate information; human review remains essential |
| **OCR sensitivity** | Performance degrades on extreme fonts, heavy stylization, sharp angles, or severe glare |
| **No semantic reasoning** | System matches text patterns, not regulatory intent or nuanced compliance edge cases |
| **Warning format not validated** | Content presence is checked, but font size, bolding, and exact layout rules are not enforced |
| **No COLA integration** | Standalone proof-of-concept per Marcus's requirements |
| **No persistence** | No audit logging, user accounts, or saved results |

These limitations are documented intentionally and align with the project's time constraints and evaluation criteria.

---

## Assumptions Made

1. **Label images are front-facing photos** of actual labels (not scans of applications)
2. **Text is predominantly English** using Latin characters
3. **Standard TTB-compliant labels** follow common formatting conventions
4. **Government warning is printed in standard fonts** (not heavily stylized)
5. **Network access not required** after initial deployment

---

## Tools & Technologies

- **Python 3.11** - Core language
- **Flask 3.0** - Web framework
- **Tesseract OCR** - Text extraction
- **Pillow (PIL)** - Image preprocessing
- **Gunicorn** - Production WSGI server
- **Docker** - Containerization
- **Render** - Hosting (free tier)

---

## Future Enhancements

If this prototype advances to production consideration:

1. **Structured OCR** - Use document layout analysis to identify label regions
2. **Cloud OCR option** - Add Google Vision/AWS Textract for higher accuracy (with caching)
3. **Warning format validation** - Check font size, bolding, and positioning
4. **Confidence calibration** - Train thresholds on larger labeled dataset
5. **Audit logging** - Track all verification decisions for compliance
6. **COLA integration** - API bridge to existing systems (requires separate authorization)

---

## License

This project was created as a take-home assessment and is provided as-is for evaluation purposes.
