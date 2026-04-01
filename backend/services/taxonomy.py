"""
Taxonomy service for medical specialties and classifications.
Manages taxonomy data from NUCC CSV or seed data.

v2 changes:
  - Added CONDITION_MAP: maps plain-language condition queries to NUCC specialties.
  - search() now checks condition map first, then falls back to specialty matching.
  - resolve() helper returns the best NUCC display string for a raw user query.
"""

import csv
import io
import logging
import threading
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from services.http_client import http_client

NUCC_CSV_URL = "https://www.nucc.org/images/stories/CSV/nucc_taxonomy_250.csv"

# Global state
_taxonomy_entries: List[Dict] = []
_taxonomy_loaded = False
_taxonomy_source = "none"
_taxonomy_lock = threading.Lock()

# ─────────────────────────────────────────────
#  CONDITION → SPECIALTY MAP
#
#  Keys are lowercase condition/symptom strings (or common prefixes/misspellings).
#  Values are lists of NUCC specialization display names to search for.
#  The first entry in each list is the "best" specialty shown to the user.
# ─────────────────────────────────────────────

CONDITION_MAP: Dict[str, List[str]] = {
    # ── Neurological ──────────────────────────────────────────────────────────
    "alzheimer":              ["Geriatric Medicine", "Neurology"],
    "alzheimers":             ["Geriatric Medicine", "Neurology"],
    "alzheimer's":            ["Geriatric Medicine", "Neurology"],
    "dementia":               ["Geriatric Medicine", "Neurology", "Psychiatry"],
    "memory loss":            ["Neurology", "Geriatric Medicine"],
    "migraine":               ["Neurology", "Pain Medicine"],
    "migraines":              ["Neurology", "Pain Medicine"],
    "headache":               ["Neurology", "Pain Medicine"],
    "cluster headache":       ["Neurology", "Pain Medicine"],
    "epilepsy":               ["Neurology"],
    "seizure":                ["Neurology"],
    "seizures":               ["Neurology"],
    "parkinson":              ["Neurology"],
    "parkinsons":             ["Neurology"],
    "parkinson's":            ["Neurology"],
    "ms":                     ["Neurology"],
    "multiple sclerosis":     ["Neurology"],
    "stroke":                 ["Neurology", "Interventional Cardiology"],
    "stroke recovery":        ["Physical Medicine & Rehabilitation", "Neurology"],
    "neuropathy":             ["Neurology", "Pain Medicine"],
    "nerve pain":             ["Pain Medicine", "Neurology"],
    "tremor":                 ["Neurology"],
    "als":                    ["Neurology"],
    "brain tumor":            ["Neurology", "Neurosurgery"],
    "concussion":             ["Neurology", "Sports Medicine"],
    "tbi":                    ["Neurology", "Physical Medicine & Rehabilitation"],
    "brain injury":           ["Neurology", "Physical Medicine & Rehabilitation"],
    "bell's palsy":           ["Neurology"],
    "meningitis":             ["Neurology", "Infectious Disease"],
    "encephalitis":           ["Neurology", "Infectious Disease"],
    "cerebral palsy":         ["Neurology", "Physical Medicine & Rehabilitation"],
    "hydrocephalus":          ["Neurosurgery", "Neurology"],
    "dizziness":              ["Neurology", "Otolaryngology"],
    "vertigo":                ["Otolaryngology", "Neurology"],
    "tinnitus":               ["Otolaryngology", "Neurology"],

    # ── Cardiac ───────────────────────────────────────────────────────────────
    "heart":                  ["Cardiovascular Disease", "Interventional Cardiology"],
    "heart disease":          ["Cardiovascular Disease", "Interventional Cardiology"],
    "heart attack":           ["Cardiovascular Disease", "Interventional Cardiology"],
    "heart failure":          ["Cardiovascular Disease"],
    "heart valve":            ["Cardiac Surgery", "Cardiovascular Disease"],
    "heart transplant":       ["Cardiac Surgery"],
    "arrhythmia":             ["Cardiovascular Disease"],
    "atrial fibrillation":    ["Cardiovascular Disease"],
    "afib":                   ["Cardiovascular Disease"],
    "hypertension":           ["Cardiovascular Disease", "Internal Medicine", "Family Medicine"],
    "high blood pressure":    ["Cardiovascular Disease", "Internal Medicine"],
    "cholesterol":            ["Cardiovascular Disease", "Internal Medicine", "Family Medicine"],
    "chest pain":             ["Cardiovascular Disease", "Emergency Medicine"],
    "pacemaker":              ["Cardiovascular Disease"],
    "coronary bypass":        ["Cardiac Surgery", "Cardiovascular Disease"],
    "cabg":                   ["Cardiac Surgery"],
    "bypass surgery":         ["Cardiac Surgery", "Cardiovascular Disease"],
    "open heart surgery":     ["Cardiac Surgery"],
    "shortness of breath":    ["Pulmonary Disease", "Cardiovascular Disease"],
    "fluid retention":        ["Nephrology", "Cardiovascular Disease"],
    "swelling":               ["Nephrology", "Cardiovascular Disease", "Vascular Surgery"],
    "pulmonary hypertension":  ["Pulmonary Disease", "Cardiovascular Disease"],
    "circulation":            ["Vascular Surgery", "Cardiovascular Disease"],

    # ── Endocrine / Metabolic ─────────────────────────────────────────────────
    "diabetes":               ["Endocrinology, Diabetes & Metabolism"],
    "diabetic":               ["Endocrinology, Diabetes & Metabolism"],
    "diabetic retinopathy":   ["Ophthalmology", "Endocrinology, Diabetes & Metabolism"],
    "thyroid":                ["Endocrinology, Diabetes & Metabolism"],
    "hypothyroid":            ["Endocrinology, Diabetes & Metabolism"],
    "hyperthyroid":           ["Endocrinology, Diabetes & Metabolism"],
    "obesity":                ["Endocrinology, Diabetes & Metabolism", "Family Medicine"],
    "weight loss":            ["Endocrinology, Diabetes & Metabolism", "Family Medicine"],
    "hormones":               ["Endocrinology, Diabetes & Metabolism"],
    "adrenal":                ["Endocrinology, Diabetes & Metabolism"],
    "pituitary":              ["Endocrinology, Diabetes & Metabolism"],
    "growth hormone":         ["Endocrinology, Diabetes & Metabolism", "Pediatrics"],
    "testosterone":           ["Endocrinology, Diabetes & Metabolism", "Urology"],
    "estrogen":               ["Endocrinology, Diabetes & Metabolism", "Obstetrics & Gynecology"],
    "metabolic syndrome":     ["Endocrinology, Diabetes & Metabolism"],
    "cushing":                ["Endocrinology, Diabetes & Metabolism"],
    "addison":                ["Endocrinology, Diabetes & Metabolism"],
    "hypoglycemia":           ["Endocrinology, Diabetes & Metabolism"],
    "insulin":                ["Endocrinology, Diabetes & Metabolism"],
    "pancreas":               ["Gastroenterology", "Endocrinology, Diabetes & Metabolism"],
    "osteoporosis":           ["Rheumatology", "Endocrinology, Diabetes & Metabolism", "Geriatric Medicine"],

    # ── Gastroenterology / GI ────────────────────────────────────────────────
    "gastro":                 ["Gastroenterology"],
    "ibs":                    ["Gastroenterology"],
    "crohn":                  ["Gastroenterology"],
    "crohns":                 ["Gastroenterology"],
    "crohn's":                ["Gastroenterology"],
    "crohns disease":         ["Gastroenterology"],
    "colitis":                ["Gastroenterology", "Colon & Rectal Surgery"],
    "ulcerative colitis":     ["Gastroenterology"],
    "colonoscopy":            ["Gastroenterology"],
    "acid reflux":            ["Gastroenterology"],
    "gerd":                   ["Gastroenterology"],
    "liver":                  ["Gastroenterology"],
    "hepatitis":              ["Gastroenterology", "Infectious Disease"],
    "fatty liver":            ["Gastroenterology"],
    "cirrhosis":              ["Gastroenterology"],
    "jaundice":               ["Gastroenterology"],
    "celiac":                 ["Gastroenterology"],
    "hemorrhoid":             ["Colon & Rectal Surgery", "Gastroenterology"],
    "hemorrhoids":            ["Colon & Rectal Surgery", "Gastroenterology"],
    "pancreatitis":           ["Gastroenterology"],
    "gallbladder":            ["General Surgery", "Gastroenterology"],
    "gallstones":             ["General Surgery", "Gastroenterology"],
    "bloating":               ["Gastroenterology"],
    "constipation":           ["Gastroenterology", "Family Medicine"],
    "diarrhea":               ["Gastroenterology", "Infectious Disease"],
    "nausea":                 ["Gastroenterology", "Family Medicine"],
    "swallowing":             ["Gastroenterology", "Otolaryngology"],
    "dysphagia":              ["Gastroenterology", "Otolaryngology"],
    "esophageal":             ["Thoracic Surgery", "Gastroenterology"],
    "esophagus":              ["Thoracic Surgery", "Gastroenterology"],

    # ── Pulmonary ─────────────────────────────────────────────────────────────
    "asthma":                 ["Pulmonary Disease", "Allergy & Immunology"],
    "copd":                   ["Pulmonary Disease"],
    "lung":                   ["Pulmonary Disease"],
    "emphysema":              ["Pulmonary Disease"],
    "sleep apnea":            ["Sleep Medicine", "Pulmonary Disease"],
    "snoring":                ["Sleep Medicine"],
    "insomnia":               ["Sleep Medicine", "Psychiatry"],
    "breathing":              ["Pulmonary Disease"],
    "pneumonia":              ["Pulmonary Disease", "Infectious Disease"],
    "bronchitis":             ["Pulmonary Disease", "Family Medicine"],
    "pulmonary fibrosis":     ["Pulmonary Disease"],
    "pleural effusion":       ["Pulmonary Disease", "Thoracic Surgery"],
    "cystic fibrosis":        ["Pulmonary Disease", "Pediatrics"],
    "wheezing":               ["Pulmonary Disease", "Allergy & Immunology"],
    "interstitial lung":      ["Pulmonary Disease"],
    "pulmonary":              ["Pulmonary Disease"],
    "respiratory":            ["Pulmonary Disease"],
    "covid":                  ["Infectious Disease", "Pulmonary Disease"],
    "tuberculosis":           ["Infectious Disease", "Pulmonary Disease"],
    "lung cancer":            ["Thoracic Surgery", "Medical Oncology", "Pulmonary Disease"],
    "pleural":                ["Thoracic Surgery", "Pulmonary Disease"],

    # ── Mental Health ─────────────────────────────────────────────────────────
    "depression":             ["Psychiatry"],
    "anxiety":                ["Psychiatry"],
    "mental":                 ["Psychiatry"],
    "bipolar":                ["Psychiatry"],
    "schizophrenia":          ["Psychiatry"],
    "adhd":                   ["Psychiatry", "Pediatrics"],
    "addiction":              ["Addiction Medicine", "Psychiatry"],
    "substance":              ["Addiction Medicine"],
    "opioid":                 ["Addiction Medicine", "Pain Medicine"],
    "alcohol":                ["Addiction Medicine"],
    "eating disorder":        ["Psychiatry"],
    "anorexia":               ["Psychiatry"],
    "bulimia":                ["Psychiatry"],
    "binge eating":           ["Psychiatry"],
    "ptsd":                   ["Psychiatry"],
    "ocd":                    ["Psychiatry"],
    "autism":                 ["Psychiatry", "Pediatrics"],
    "asperger":               ["Psychiatry", "Pediatrics"],
    "panic attack":           ["Psychiatry"],
    "panic disorder":         ["Psychiatry"],
    "phobia":                 ["Psychiatry"],
    "social anxiety":         ["Psychiatry"],
    "borderline personality": ["Psychiatry"],
    "personality disorder":   ["Psychiatry"],
    "mania":                  ["Psychiatry"],
    "psychosis":              ["Psychiatry"],
    "hallucinations":         ["Psychiatry"],
    "grief":                  ["Psychiatry"],
    "trauma":                 ["Psychiatry", "Emergency Medicine"],
    "postpartum depression":  ["Psychiatry", "Obstetrics & Gynecology"],

    # ── Musculoskeletal / Pain ────────────────────────────────────────────────
    "arthritis":              ["Rheumatology", "Orthopaedic Surgery"],
    "rheumatoid":             ["Rheumatology"],
    "lupus":                  ["Rheumatology"],
    "fibromyalgia":           ["Rheumatology", "Pain Medicine"],
    "gout":                   ["Rheumatology"],
    "sjogren":                ["Rheumatology"],
    "scleroderma":            ["Rheumatology"],
    "vasculitis":             ["Rheumatology"],
    "myositis":               ["Rheumatology"],
    "polymyalgia":            ["Rheumatology"],
    "ankylosing spondylitis": ["Rheumatology"],
    "reactive arthritis":     ["Rheumatology"],
    "psoriatic arthritis":    ["Rheumatology", "Dermatology"],
    "raynaud":                ["Rheumatology", "Vascular Surgery"],
    "autoimmune":             ["Rheumatology", "Allergy & Immunology"],
    "back pain":              ["Pain Medicine", "Orthopaedic Surgery", "Physical Medicine & Rehabilitation"],
    "lower back pain":        ["Pain Medicine", "Orthopaedic Surgery"],
    "neck pain":              ["Pain Medicine", "Orthopaedic Surgery"],
    "sciatica":               ["Pain Medicine", "Orthopaedic Surgery", "Neurology"],
    "spine":                  ["Orthopaedic Surgery", "Neurosurgery"],
    "spinal":                 ["Orthopaedic Surgery", "Neurosurgery", "Pain Medicine"],
    "knee":                   ["Orthopaedic Surgery", "Sports Medicine"],
    "hip":                    ["Orthopaedic Surgery"],
    "shoulder":               ["Orthopaedic Surgery", "Sports Medicine"],
    "fracture":               ["Orthopaedic Surgery"],
    "stress fracture":        ["Sports Medicine", "Orthopaedic Surgery"],
    "sports injury":          ["Sports Medicine", "Orthopaedic Surgery"],
    "tendon":                 ["Sports Medicine", "Orthopaedic Surgery"],
    "tendonitis":             ["Sports Medicine", "Orthopaedic Surgery"],
    "ligament":               ["Sports Medicine", "Orthopaedic Surgery"],
    "acl":                    ["Sports Medicine", "Orthopaedic Surgery"],
    "rotator cuff":           ["Sports Medicine", "Orthopaedic Surgery"],
    "shin splints":           ["Sports Medicine"],
    "sprain":                 ["Sports Medicine", "Orthopaedic Surgery"],
    "athletic":               ["Sports Medicine"],
    "joint":                  ["Rheumatology", "Orthopaedic Surgery"],
    "scoliosis":              ["Orthopaedic Surgery", "Neurosurgery"],
    "chronic pain":           ["Pain Medicine"],
    "pain management":        ["Pain Medicine"],
    "phantom pain":           ["Pain Medicine"],
    "crps":                   ["Pain Medicine"],
    "complex regional pain":  ["Pain Medicine"],
    "epidural":               ["Anesthesiology"],
    "nerve block":            ["Anesthesiology", "Pain Medicine"],
    "pain block":             ["Anesthesiology", "Pain Medicine"],

    # ── Cancer / Oncology ─────────────────────────────────────────────────────
    "cancer":                 ["Medical Oncology", "Hematology & Oncology"],
    "tumor":                  ["Medical Oncology", "Radiation Oncology"],
    "oncology":               ["Medical Oncology", "Hematology & Oncology"],
    "leukemia":               ["Hematology & Oncology"],
    "lymphoma":               ["Hematology & Oncology"],
    "myeloma":                ["Hematology & Oncology"],
    "multiple myeloma":       ["Hematology & Oncology"],
    "blood cancer":           ["Hematology & Oncology"],
    "bone marrow":            ["Hematology & Oncology"],
    "sickle cell":            ["Hematology & Oncology"],
    "hemophilia":             ["Hematology & Oncology"],
    "thalassemia":            ["Hematology & Oncology"],
    "platelets":              ["Hematology & Oncology"],
    "breast cancer":          ["Medical Oncology", "Radiation Oncology"],
    "prostate cancer":        ["Medical Oncology", "Urology"],
    "cervical cancer":        ["Obstetrics & Gynecology", "Medical Oncology"],
    "ovarian cancer":         ["Obstetrics & Gynecology", "Medical Oncology"],
    "kidney cancer":          ["Urology", "Medical Oncology"],
    "skin cancer":            ["Dermatology", "Medical Oncology"],
    "head and neck cancer":   ["Otolaryngology", "Medical Oncology"],
    "chemotherapy":           ["Medical Oncology"],
    "radiation":              ["Radiation Oncology"],
    "biopsy":                 ["Medical Oncology"],
    "breast reconstruction":  ["Plastic Surgery", "Medical Oncology"],

    # ── Kidney / Urology ──────────────────────────────────────────────────────
    "kidney":                 ["Nephrology", "Urology"],
    "kidney disease":         ["Nephrology"],
    "kidney stone":           ["Urology", "Nephrology"],
    "kidney stones":          ["Urology", "Nephrology"],
    "dialysis":               ["Nephrology"],
    "ckd":                    ["Nephrology"],
    "renal failure":          ["Nephrology"],
    "acute kidney injury":    ["Nephrology"],
    "aki":                    ["Nephrology"],
    "chronic kidney":         ["Nephrology"],
    "proteinuria":            ["Nephrology"],
    "urinary":                ["Urology"],
    "bladder":                ["Urology"],
    "prostate":               ["Urology"],
    "incontinence":           ["Urology"],
    "overactive bladder":     ["Urology"],
    "erectile dysfunction":   ["Urology"],
    "ed":                     ["Urology"],
    "vasectomy":              ["Urology"],
    "testicular":             ["Urology"],
    "uti":                    ["Urology", "Infectious Disease"],
    "urinary tract infection": ["Urology", "Infectious Disease"],
    "sexual health":          ["Urology", "Obstetrics & Gynecology"],
    "male health":            ["Urology"],

    # ── Women's Health ────────────────────────────────────────────────────────
    "gynecology":             ["Obstetrics & Gynecology"],
    "pregnancy":              ["Obstetrics & Gynecology"],
    "prenatal":               ["Obstetrics & Gynecology"],
    "fertility":              ["Obstetrics & Gynecology"],
    "menopause":              ["Obstetrics & Gynecology", "Endocrinology, Diabetes & Metabolism"],
    "pcos":                   ["Obstetrics & Gynecology", "Endocrinology, Diabetes & Metabolism"],
    "endometriosis":          ["Obstetrics & Gynecology"],
    "ovarian cyst":           ["Obstetrics & Gynecology"],
    "uterine fibroids":       ["Obstetrics & Gynecology"],
    "fibroids":               ["Obstetrics & Gynecology"],
    "irregular periods":      ["Obstetrics & Gynecology"],
    "heavy periods":          ["Obstetrics & Gynecology"],
    "birth control":          ["Obstetrics & Gynecology", "Family Medicine"],
    "miscarriage":            ["Obstetrics & Gynecology"],
    "postpartum":             ["Obstetrics & Gynecology", "Psychiatry"],
    "womens health":          ["Obstetrics & Gynecology"],
    "women's health":         ["Obstetrics & Gynecology"],
    "mammogram":              ["Diagnostic Radiology"],

    # ── Eyes / Ophthalmology ──────────────────────────────────────────────────
    "eye":                    ["Ophthalmology"],
    "vision":                 ["Ophthalmology"],
    "glaucoma":               ["Ophthalmology"],
    "cataract":               ["Ophthalmology"],
    "cataracts":              ["Ophthalmology"],
    "dry eyes":               ["Ophthalmology"],
    "macular degeneration":   ["Ophthalmology"],
    "retina":                 ["Ophthalmology"],
    "conjunctivitis":         ["Ophthalmology"],
    "pink eye":               ["Ophthalmology"],
    "lazy eye":               ["Ophthalmology"],
    "strabismus":             ["Ophthalmology"],
    "cornea":                 ["Ophthalmology"],

    # ── ENT / Otolaryngology ──────────────────────────────────────────────────
    "ent":                    ["Otolaryngology"],
    "ear":                    ["Otolaryngology"],
    "nose":                   ["Otolaryngology"],
    "throat":                 ["Otolaryngology"],
    "sinus":                  ["Otolaryngology", "Allergy & Immunology"],
    "tonsils":                ["Otolaryngology"],
    "tonsillitis":            ["Otolaryngology"],
    "adenoids":               ["Otolaryngology", "Pediatrics"],
    "deviated septum":        ["Otolaryngology"],
    "hoarseness":             ["Otolaryngology"],
    "voice":                  ["Otolaryngology"],
    "larynx":                 ["Otolaryngology"],
    "balance":                ["Otolaryngology", "Neurology"],
    "hearing":                ["Audiologist"],
    "hearing loss":           ["Audiologist"],

    # ── Allergy / Immunology ──────────────────────────────────────────────────
    "allergy":                ["Allergy & Immunology"],
    "allergies":              ["Allergy & Immunology"],
    "food allergy":           ["Allergy & Immunology"],
    "drug allergy":           ["Allergy & Immunology"],
    "latex allergy":          ["Allergy & Immunology"],
    "anaphylaxis":            ["Allergy & Immunology", "Emergency Medicine"],
    "hay fever":              ["Allergy & Immunology"],
    "rhinitis":               ["Allergy & Immunology", "Otolaryngology"],
    "hives":                  ["Dermatology", "Allergy & Immunology"],
    "immune":                 ["Allergy & Immunology", "Infectious Disease"],
    "immunology":             ["Allergy & Immunology"],
    "immunodeficiency":       ["Allergy & Immunology", "Infectious Disease"],
    "wheezing":               ["Pulmonary Disease", "Allergy & Immunology"],

    # ── Dermatology / Skin ────────────────────────────────────────────────────
    "skin":                   ["Dermatology"],
    "acne":                   ["Dermatology"],
    "rash":                   ["Dermatology"],
    "eczema":                 ["Dermatology", "Allergy & Immunology"],
    "psoriasis":              ["Dermatology", "Rheumatology"],
    "melanoma":               ["Dermatology", "Medical Oncology"],
    "warts":                  ["Dermatology"],
    "moles":                  ["Dermatology"],
    "hair loss":              ["Dermatology"],
    "alopecia":               ["Dermatology"],
    "vitiligo":               ["Dermatology"],
    "shingles":               ["Dermatology", "Infectious Disease"],
    "scar":                   ["Plastic Surgery", "Dermatology"],

    # ── Infection / Blood ─────────────────────────────────────────────────────
    "hiv":                    ["Infectious Disease"],
    "aids":                   ["Infectious Disease"],
    "infection":              ["Infectious Disease"],
    "anemia":                 ["Hematology & Oncology"],
    "blood disorder":         ["Hematology & Oncology"],
    "clotting":               ["Hematology & Oncology"],
    "blood clot":             ["Vascular Surgery", "Hematology & Oncology"],
    "deep vein thrombosis":   ["Vascular Surgery", "Hematology & Oncology"],
    "dvt":                    ["Vascular Surgery", "Hematology & Oncology"],
    "tb":                     ["Infectious Disease"],
    "lyme":                   ["Infectious Disease"],
    "lyme disease":           ["Infectious Disease"],
    "malaria":                ["Infectious Disease"],
    "sepsis":                 ["Infectious Disease"],
    "mrsa":                   ["Infectious Disease"],
    "fungal infection":       ["Infectious Disease", "Dermatology"],
    "flu":                    ["Infectious Disease", "Family Medicine"],
    "influenza":              ["Infectious Disease", "Family Medicine"],
    "mononucleosis":          ["Infectious Disease"],
    "mono":                   ["Infectious Disease"],
    "std":                    ["Infectious Disease"],
    "sti":                    ["Infectious Disease"],
    "sexually transmitted":   ["Infectious Disease"],

    # ── Vascular Surgery ──────────────────────────────────────────────────────
    "vascular":               ["Vascular Surgery"],
    "aortic aneurysm":        ["Vascular Surgery"],
    "aneurysm":               ["Vascular Surgery"],
    "peripheral artery":      ["Vascular Surgery"],
    "peripheral vascular":    ["Vascular Surgery"],
    "varicose veins":         ["Vascular Surgery"],
    "carotid":                ["Vascular Surgery", "Neurology"],

    # ── Thoracic Surgery ──────────────────────────────────────────────────────
    "thoracic":               ["Thoracic Surgery"],
    "chest surgery":          ["Thoracic Surgery", "Cardiac Surgery"],
    "mediastinum":            ["Thoracic Surgery"],

    # ── General Surgery ───────────────────────────────────────────────────────
    "appendicitis":           ["General Surgery"],
    "appendix":               ["General Surgery"],
    "hernia":                 ["General Surgery"],
    "abscess":                ["General Surgery", "Infectious Disease"],
    "wound":                  ["Emergency Medicine", "General Surgery"],

    # ── Plastic Surgery ───────────────────────────────────────────────────────
    "plastic surgery":        ["Plastic Surgery"],
    "cosmetic surgery":       ["Plastic Surgery"],
    "reconstruction":         ["Plastic Surgery"],
    "burn":                   ["Plastic Surgery", "Emergency Medicine"],
    "burns":                  ["Plastic Surgery", "Emergency Medicine"],
    "cleft palate":           ["Plastic Surgery", "Pediatrics"],
    "rhinoplasty":            ["Plastic Surgery"],

    # ── Anesthesiology ────────────────────────────────────────────────────────
    "anesthesia":             ["Anesthesiology"],
    "anesthesiology":         ["Anesthesiology"],
    "sedation":               ["Anesthesiology"],

    # ── Diagnostic Radiology ──────────────────────────────────────────────────
    "mri":                    ["Diagnostic Radiology"],
    "ct scan":                ["Diagnostic Radiology"],
    "x-ray":                  ["Diagnostic Radiology"],
    "ultrasound":             ["Diagnostic Radiology"],
    "imaging":                ["Diagnostic Radiology"],

    # ── Emergency Medicine ────────────────────────────────────────────────────
    "emergency":              ["Emergency Medicine"],
    "overdose":               ["Emergency Medicine", "Addiction Medicine"],
    "poisoning":              ["Emergency Medicine"],
    "laceration":             ["Emergency Medicine"],

    # ── Physical Medicine & Rehabilitation ────────────────────────────────────
    "physical therapy":       ["Physical Medicine & Rehabilitation"],
    "rehabilitation":         ["Physical Medicine & Rehabilitation"],
    "rehab":                  ["Physical Medicine & Rehabilitation"],
    "occupational therapy":   ["Physical Medicine & Rehabilitation"],
    "mobility":               ["Physical Medicine & Rehabilitation"],
    "prosthetics":            ["Physical Medicine & Rehabilitation"],

    # ── Pediatrics ────────────────────────────────────────────────────────────
    "child":                  ["Pediatrics"],
    "children":               ["Pediatrics"],
    "infant":                 ["Pediatrics"],
    "baby":                   ["Pediatrics"],
    "newborn":                ["Pediatrics"],
    "pediatric":              ["Pediatrics"],
    "vaccination":            ["Pediatrics", "Family Medicine"],
    "vaccine":                ["Pediatrics", "Family Medicine"],
    "developmental delay":    ["Pediatrics"],
    "growth disorder":        ["Pediatrics", "Endocrinology, Diabetes & Metabolism"],

    # ── Allied Health / Non-Physician Providers ───────────────────────────────
    "dentist":                ["Dentist"],
    "dental":                 ["Dentist"],
    "teeth":                  ["Dentist"],
    "tooth":                  ["Dentist"],
    "dental hygiene":         ["Dental Hygienist"],
    "root canal":             ["Endodontics"],
    "oral surgery":           ["Oral and Maxillofacial Surgery"],
    "jaw":                    ["Oral and Maxillofacial Surgery"],
    "braces":                 ["Orthodontics and Dentofacial Orthopedics"],
    "orthodontics":           ["Orthodontics and Dentofacial Orthopedics"],
    "pediatric dentist":      ["Pediatric Dentistry"],
    "gum disease":            ["Periodontics"],
    "gums":                   ["Periodontics"],
    "dentures":               ["Prosthodontics"],
    "implants":               ["Prosthodontics"],
    "foot":                   ["Podiatrist"],
    "feet":                   ["Podiatrist"],
    "podiatry":               ["Podiatrist"],
    "bunion":                 ["Podiatrist"],
    "plantar fasciitis":      ["Podiatrist"],
    "pharmacist":             ["Pharmacist"],
    "pharmacy":               ["Pharmacist"],
    "medication":             ["Pharmacist", "Family Medicine"],
    "midwife":                ["Certified Nurse Midwife"],
    "nurse anesthetist":      ["Certified Registered Nurse Anesthetist"],
    "nurse practitioner":     ["Nurse Practitioner"],
    "np":                     ["Nurse Practitioner"],
    "physician assistant":    ["Physician Assistant"],
    "pa":                     ["Physician Assistant"],
    "optometrist":            ["Optometrist"],
    "eye exam":               ["Optometrist"],
    "glasses":                ["Optometrist"],
    "contacts":               ["Optometrist"],
    "chiropractor":           ["Chiropractor"],
    "chiropractic":           ["Chiropractor"],
    "adjustment":             ["Chiropractor"],
    "physical therapist":     ["Physical Therapist"],
    "occupational therapist": ["Occupational Therapist"],
    "speech therapy":         ["Speech-Language Pathologist"],
    "speech language":        ["Speech-Language Pathologist"],
    "stuttering":             ["Speech-Language Pathologist"],
    "therapist":              ["Counselor", "Psychologist", "Marriage & Family Therapist"],
    "counselor":              ["Counselor"],
    "counseling":             ["Counselor"],
    "psychologist":           ["Psychologist"],
    "psychology":             ["Psychologist"],
    "social worker":          ["Social Worker, Clinical"],
    "dietitian":              ["Dietitian, Registered"],
    "nutritionist":           ["Dietitian, Registered"],
    "nutrition":              ["Dietitian, Registered"],
    "respiratory therapist":  ["Respiratory Therapist"],
    "urgent care":            ["Urgent Care"],
    "walk in":                ["Urgent Care"],
    "walk-in":                ["Urgent Care"],
    "ambulatory":             ["Ambulatory Surgical"],

    # ── General / Geriatric / Primary Care ────────────────────────────────────
    "geriatric":              ["Geriatric Medicine"],
    "elderly":                ["Geriatric Medicine"],
    "aging":                  ["Geriatric Medicine"],
    "senior":                 ["Geriatric Medicine"],
    "primary care":           ["Family Medicine", "Internal Medicine", "General Practice"],
    "general":                ["General Practice", "Family Medicine"],
    "preventive":             ["Family Medicine", "Internal Medicine"],
    "checkup":                ["Family Medicine", "Internal Medicine", "General Practice"],
}


# ─────────────────────────────────────────────
#  SEED TAXONOMY
# ─────────────────────────────────────────────

_SEED_TAXONOMY = [
    ("Allopathic & Osteopathic Physicians", "Addiction Medicine"),
    ("Allopathic & Osteopathic Physicians", "Allergy & Immunology"),
    ("Allopathic & Osteopathic Physicians", "Anesthesiology"),
    ("Allopathic & Osteopathic Physicians", "Cardiac Surgery"),
    ("Allopathic & Osteopathic Physicians", "Cardiovascular Disease"),
    ("Allopathic & Osteopathic Physicians", "Colon & Rectal Surgery"),
    ("Allopathic & Osteopathic Physicians", "Dermatology"),
    ("Allopathic & Osteopathic Physicians", "Diagnostic Radiology"),
    ("Allopathic & Osteopathic Physicians", "Emergency Medicine"),
    ("Allopathic & Osteopathic Physicians", "Endocrinology, Diabetes & Metabolism"),
    ("Allopathic & Osteopathic Physicians", "Family Medicine"),
    ("Allopathic & Osteopathic Physicians", "Gastroenterology"),
    ("Allopathic & Osteopathic Physicians", "General Practice"),
    ("Allopathic & Osteopathic Physicians", "General Surgery"),
    ("Allopathic & Osteopathic Physicians", "Geriatric Medicine"),
    ("Allopathic & Osteopathic Physicians", "Hematology & Oncology"),
    ("Allopathic & Osteopathic Physicians", "Infectious Disease"),
    ("Allopathic & Osteopathic Physicians", "Internal Medicine"),
    ("Allopathic & Osteopathic Physicians", "Interventional Cardiology"),
    ("Allopathic & Osteopathic Physicians", "Medical Oncology"),
    ("Allopathic & Osteopathic Physicians", "Nephrology"),
    ("Allopathic & Osteopathic Physicians", "Neurology"),
    ("Allopathic & Osteopathic Physicians", "Neurosurgery"),
    ("Allopathic & Osteopathic Physicians", "Obstetrics & Gynecology"),
    ("Allopathic & Osteopathic Physicians", "Ophthalmology"),
    ("Allopathic & Osteopathic Physicians", "Orthopaedic Surgery"),
    ("Allopathic & Osteopathic Physicians", "Otolaryngology"),
    ("Allopathic & Osteopathic Physicians", "Pain Medicine"),
    ("Allopathic & Osteopathic Physicians", "Pediatrics"),
    ("Allopathic & Osteopathic Physicians", "Physical Medicine & Rehabilitation"),
    ("Allopathic & Osteopathic Physicians", "Plastic Surgery"),
    ("Allopathic & Osteopathic Physicians", "Psychiatry"),
    ("Allopathic & Osteopathic Physicians", "Pulmonary Disease"),
    ("Allopathic & Osteopathic Physicians", "Radiation Oncology"),
    ("Allopathic & Osteopathic Physicians", "Rheumatology"),
    ("Allopathic & Osteopathic Physicians", "Sleep Medicine"),
    ("Allopathic & Osteopathic Physicians", "Sports Medicine"),
    ("Allopathic & Osteopathic Physicians", "Thoracic Surgery"),
    ("Allopathic & Osteopathic Physicians", "Urology"),
    ("Allopathic & Osteopathic Physicians", "Vascular Surgery"),
    ("Dental Providers", "Dentist"),
    ("Dental Providers", "Dental Hygienist"),
    ("Dental Providers", "Endodontics"),
    ("Dental Providers", "Oral and Maxillofacial Surgery"),
    ("Dental Providers", "Orthodontics and Dentofacial Orthopedics"),
    ("Dental Providers", "Pediatric Dentistry"),
    ("Dental Providers", "Periodontics"),
    ("Dental Providers", "Prosthodontics"),
    ("Podiatric Medicine & Surgery Providers", "Podiatrist"),
    ("Pharmacy Service Providers", "Pharmacist"),
    ("Pharmacy Service Providers", "Clinical Pharmacy Specialist"),
    ("Nursing Service Providers", "Certified Nurse Midwife"),
    ("Nursing Service Providers", "Certified Registered Nurse Anesthetist"),
    ("Nursing Service Providers", "Clinical Nurse Specialist"),
    ("Nursing Service Providers", "Licensed Practical Nurse"),
    ("Nursing Service Providers", "Nurse Practitioner"),
    ("Nursing Service Providers", "Registered Nurse"),
    ("Physician Assistants & Advanced Practice Nursing Providers", "Physician Assistant"),
    ("Eye and Vision Services Providers", "Optometrist"),
    ("Chiropractic Providers", "Chiropractor"),
    ("Physical Medicine & Rehabilitation Providers", "Physical Therapist"),
    ("Physical Medicine & Rehabilitation Providers", "Occupational Therapist"),
    ("Respiratory, Developmental, Rehabilitative & Restorative Service Providers", "Respiratory Therapist"),
    ("Speech, Language and Hearing Service Providers", "Audiologist"),
    ("Speech, Language and Hearing Service Providers", "Speech-Language Pathologist"),
    ("Behavioral Health & Social Service Providers", "Counselor"),
    ("Behavioral Health & Social Service Providers", "Marriage & Family Therapist"),
    ("Behavioral Health & Social Service Providers", "Psychologist"),
    ("Behavioral Health & Social Service Providers", "Social Worker"),
    ("Behavioral Health & Social Service Providers", "Social Worker, Clinical"),
    ("Dietetic & Nutritional Service Providers", "Dietitian, Registered"),
    ("Emergency Medical Service Providers", "Emergency Medical Technician"),
    ("Emergency Medical Service Providers", "Paramedic"),
    ("Ambulatory Health Care Facilities", "Ambulatory Surgical"),
    ("Ambulatory Health Care Facilities", "Urgent Care"),
    ("Hospital", "General Acute Care Hospital"),
]


def _build_entries(rows: List[tuple]) -> List[Dict]:
    """Build taxonomy entries from classification/specialization tuples."""
    out, seen = [], set()
    for classification, specialization in rows:
        c = (classification or "").strip()
        s = (specialization or "").strip()
        if not c:
            continue
        display = s if s else c
        if display in seen:
            continue
        seen.add(display)
        out.append({
            "classification": c,
            "specialization": s,
            "display": display,
            "search_text": f"{c} {s}".lower(),
        })
    return out


def _load_taxonomy_background() -> None:
    """Background thread to load taxonomy from NUCC CSV."""
    global _taxonomy_loaded, _taxonomy_source

    seed = _build_entries(_SEED_TAXONOMY)
    with _taxonomy_lock:
        _taxonomy_entries[:] = seed
        _taxonomy_loaded = True
        _taxonomy_source = "seed"
    logger.info("Taxonomy seed ready: %d entries", len(seed))

    try:
        resp = http_client.get(NUCC_CSV_URL, timeout=30)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = [
            (r.get("Classification", "").strip(), r.get("Specialization", "").strip())
            for r in reader
            if r.get("Classification", "").strip()
        ]
        if rows:
            live = _build_entries(rows)
            with _taxonomy_lock:
                _taxonomy_entries[:] = live
                _taxonomy_source = "NUCC CSV"
            logger.info("NUCC CSV loaded: %d entries", len(live))
    except Exception as e:
        logger.warning("NUCC CSV fetch failed: %s — keeping seed", e)


def initialize() -> None:
    """Start background thread to load taxonomy data."""
    threading.Thread(target=_load_taxonomy_background, daemon=True, name="tax-loader").start()


# ─────────────────────────────────────────────
#  CONDITION MAP LOOKUP
# ─────────────────────────────────────────────

def _condition_map_lookup(q: str) -> Optional[List[str]]:
    """
    Check if q (or any prefix of it) matches a key in CONDITION_MAP.
    Prefix matching lets "alzh", "alzhe", "alzheim" all resolve to "alzheimer".

    When multiple keys start with q (e.g. q="heart" matches both "heart" and
    "heart failure"), we prefer the LONGEST matching key so that more-specific
    multi-word entries are not shadowed by shorter single-word ones.

    Returns list of specialty display names, or None if no match.
    """
    q = q.lower().strip()
    # Exact match first — always wins
    if q in CONDITION_MAP:
        return CONDITION_MAP[q]
    # Prefix match: collect ALL keys that start with q (min 3 chars to avoid noise),
    # then return the mapping for the longest one (most specific).
    if len(q) >= 3:
        candidates = [key for key in CONDITION_MAP if key.startswith(q)]
        if candidates:
            best_key = max(candidates, key=len)
            return CONDITION_MAP[best_key]
    return None


# ─────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────

def search(q: str, limit: int = 12) -> List[Dict]:
    """
    Search taxonomy for matching specialties.

    Priority:
      1. Condition map lookup (plain-language conditions → specialties)
      2. Direct specialty name matching against NUCC entries

    Args:
        q: Search query string (specialty name or condition/symptom)
        limit: Maximum results to return

    Returns:
        List of matching taxonomy entry dicts with 'display' and 'classification'.
    """
    q_stripped = q.strip()
    if not q_stripped:
        return []

    # ── Step 1: condition map ──────────────────────────────────────────────
    condition_specialties = _condition_map_lookup(q_stripped)
    if condition_specialties:
        with _taxonomy_lock:
            entries_snapshot = list(_taxonomy_entries)
        results = []
        seen = set()
        for specialty_name in condition_specialties:
            for e in entries_snapshot:
                if e["display"].lower() == specialty_name.lower() and e["display"] not in seen:
                    seen.add(e["display"])
                    results.append({"display": e["display"], "classification": e["classification"]})
                    break
        if results:
            return results[:limit]

    # ── Step 2: specialty name matching (original logic) ───────────────────
    q_lower = q_stripped.lower()
    q_words = [w for w in q_lower.split() if len(w) >= 2]

    with _taxonomy_lock:
        entries = list(_taxonomy_entries)

    scored: List[tuple] = []
    seen: set = set()

    for e in entries:
        st = e["search_text"]
        d = e["display"]
        score = 0

        if q_lower == e["specialization"].lower():
            score = 100
        elif e["specialization"].lower().startswith(q_lower):
            score = 85
        elif e["classification"].lower().startswith(q_lower):
            score = 75
        elif q_lower in st:
            score = 60
        elif all(w in st for w in q_words):
            score = 50
        elif any(w in st for w in q_words):
            score = 30

        if score > 0 and d not in seen:
            seen.add(d)
            scored.append((score, d, e["classification"]))

    return [
        {"display": display, "classification": classification}
        for _, display, classification in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]
    ]


def resolve(q: str) -> str:
    """
    Resolve a user query to the best single NUCC specialty display name.
    Used by the search route when sending taxonomy_description to NPPES.

    Returns the best match display string, or q itself as fallback.
    """
    matches = search(q, limit=1)
    return matches[0]["display"] if matches else q


def is_loaded() -> bool:
    """Check if taxonomy is loaded."""
    return _taxonomy_loaded


def source() -> str:
    """Get source of loaded taxonomy data."""
    return _taxonomy_source


def count() -> int:
    """Get number of taxonomy entries."""
    with _taxonomy_lock:
        return len(_taxonomy_entries)