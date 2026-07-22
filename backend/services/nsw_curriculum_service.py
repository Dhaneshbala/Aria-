"""
NSW Department of Education Curriculum Service
────────────────────────────────────────────────
Contains the NSW Education Standards Authority (NESA) syllabus structure:
  • Key Learning Areas (KLAs)
  • Stages (Early Stage 1 → Stage 6)
  • Subjects and their codes
  • Curriculum outcomes per stage
  • Content descriptors
  • HSC subject structures

Reference: https://education.nsw.gov.au/curriculum/learning-7-12
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".aria_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CURRICULUM_CACHE = DATA_DIR / "nsw_curriculum.json"


# ── NSW Curriculum Structure ──────────────────────────────────────────────────

NSW_STAGES = {
    "ES1": {"name": "Early Stage 1", "ages": "4-5", "years": "K"},
    "S1": {"name": "Stage 1", "ages": "5-7", "years": "1-2"},
    "S2": {"name": "Stage 2", "ages": "7-9", "years": "3-4"},
    "S3": {"name": "Stage 3", "ages": "9-11", "years": "5-6"},
    "S4": {"name": "Stage 4", "ages": "11-14", "years": "7-8"},
    "S5": {"name": "Stage 5", "ages": "14-16", "years": "9-10"},
    "S6": {"name": "Stage 6", "ages": "16-18", "years": "11-12 (HSC)"},
}

NSW_KLAS = {
    "english": {
        "name": "English",
        "code": "EN",
        "stages": {
            "ES1": ["EN1-1A", "EN1-2A", "EN1-3A", "EN1-4A", "EN1-5A", "EN1-6A", "EN1-7A", "EN1-8A", "EN1-9A", "EN1-10A", "EN1-11A"],
            "S1": ["EN1-1A", "EN1-2A", "EN1-3A", "EN1-4A", "EN1-5A", "EN1-6A", "EN1-7A", "EN1-8A", "EN1-9A", "EN1-10A", "EN1-11A"],
            "S2": ["EN2-6A", "EN2-7A", "EN2-8A", "EN2-9A", "EN2-10A", "EN2-11A", "EN2-12A", "EN2-13A", "EN2-14A", "EN2-15A"],
            "S3": ["EN3-6A", "EN3-7A", "EN3-8A", "EN3-9A", "EN3-10A", "EN3-11A", "EN3-12A", "EN3-13A", "EN3-14A"],
            "S4": ["EN4-1A", "EN4-2A", "EN4-3A", "EN4-4A", "EN4-5A", "EN4-6A", "EN4-7A", "EN4-8A", "EN4-9A", "EN4-10A"],
            "S5": ["EN5-1A", "EN5-2A", "EN5-3A", "EN5-4A", "EN5-5A", "EN5-6A", "EN5-7A", "EN5-8A", "EN5-9A", "EN5-10A"],
            "S6": ["EN11-1A", "EN11-2A", "EN11-3A", "EN11-4A", "EN11-5A", "EN12-1A", "EN12-2A", "EN12-3A", "EN12-4A", "EN12-5A"],
        },
        "content": {
            "S4": [
                "Responding to and composing a wide range of texts",
                "Understanding and using language",
                "Thinking critically and interpretively",
                "Analyzing, evaluating and comparing texts",
                "Creating a range of text types",
            ],
            "S5": [
                "Responding to and composing texts of all modes",
                "Understanding and using language",
                "Thinking critically and interpretively about texts",
                "Analysing, evaluating and comparing texts",
                "Creating a range of text types for different purposes and audiences",
            ],
            "S6": [
                "Advanced responding to and composing texts",
                "Critical analysis and evaluation",
                "Research and inquiry",
                "Creating extended compositions",
            ],
        },
    },
    "mathematics": {
        "name": "Mathematics",
        "code": "MA",
        "stages": {
            "ES1": ["MA1-1WM", "MA1-2WM", "MA1-3WM", "MA1-1AN", "MA1-2AN", "MA1-3AN", "MA1-1MG", "MA1-2MG", "MA1-3MG", "MA1-4NA", "MA1-5NA", "MA1-6NA", "MA1-7N", "MA1-8N", "MA1-9M", "MA1-10M", "MA1-11M", "MA1-12M", "MA1-13M", "MA1-14M", "MA1-15M", "MA1-16M", "MA1-17M", "MA1-18M", "MA1-19M", "MA1-20M", "MA1-1PS", "MA1-2PS", "MA1-3PS", "MA1-4PS"],
            "S1": ["MA1-1WM", "MA1-2WM", "MA1-3WM", "MA1-1AN", "MA1-2AN", "MA1-3AN", "MA1-1MG", "MA1-2MG", "MA1-3MG", "MA1-4NA", "MA1-5NA", "MA1-6NA", "MA1-7N", "MA1-8N", "MA1-9M", "MA1-10M", "MA1-11M", "MA1-12M", "MA1-13M", "MA1-14M", "MA1-15M", "MA1-16M", "MA1-17M", "MA1-18M", "MA1-19M", "MA1-20M", "MA1-1PS", "MA1-2PS", "MA1-3PS", "MA1-4PS"],
            "S2": ["MA2-1WM", "MA2-2WM", "MA2-3WM", "MA2-1AN", "MA2-2AN", "MA2-3AN", "MA2-1MG", "MA2-2MG", "MA2-3MG", "MA2-4NA", "MA2-5NA", "MA2-6NA", "MA2-7N", "MA2-8N", "MA2-9M", "MA2-10M", "MA2-11M", "MA2-12M", "MA2-13M", "MA2-14M", "MA2-15M", "MA2-16M", "MA2-17M", "MA2-18M", "MA2-19M", "MA2-20M", "MA2-21M", "MA2-22M", "MA2-1PS", "MA2-2PS", "MA2-3PS", "MA2-4PS"],
            "S3": ["MA3-1WM", "MA3-2WM", "MA3-3WM", "MA3-1AN", "MA3-2AN", "MA3-3AN", "MA3-1MG", "MA3-2MG", "MA3-3MG", "MA3-4NA", "MA3-5NA", "MA3-6NA", "MA3-7N", "MA3-8N", "MA3-9M", "MA3-10M", "MA3-11M", "MA3-12M", "MA3-13M", "MA3-14M", "MA3-15M", "MA3-16M", "MA3-17M", "MA3-18M", "MA3-19M", "MA3-20M", "MA3-21M", "MA3-22M", "MA3-1DS", "MA3-2DS", "MA3-1MM", "MA3-2MM", "MA3-3MM", "MA3-1PS", "MA3-2PS"],
            "S4": ["MA4-1WM", "MA4-2WM", "MA4-3WM", "MA4-1AN", "MA4-2AN", "MA4-1DS", "MA4-2DS", "MA4-3DS", "MA4-4NA", "MA4-5NA", "MA4-1MG", "MA4-2MG", "MA4-3MG", "MA4-4MG", "MA4-1M", "MA4-2M", "MA4-3M", "MA4-1A", "MA4-2A", "MA4-3A", "MA4-4A", "MA4-5A", "MA4-6A", "MA4-7A", "MA4-1N", "MA4-2N", "MA4-3N", "MA4-4N", "MA4-5N", "MA4-6N", "MA4-7N", "MA4-8N", "MA4-1P", "MA4-2P", "MA4-3P", "MA4-4P", "MA4-5P", "MA4-6P", "MA4-7P"],
            "S5": ["MA5-1WM", "MA5-2WM", "MA5-3WM", "MA5-1AN", "MA5-2AN", "MA5-1DS", "MA5-2DS", "MA5-3DS", "MA5-1A", "MA5-2A", "MA5-3A", "MA5-4A", "MA5-5A", "MA5-6A", "MA5-7A", "MA5-8A", "MA5-1M", "MA5-2M", "MA5-3M", "MA5-4M", "MA5-5M", "MA5-6M", "MA5-7M", "MA5-8M", "MA5-1MG", "MA5-2MG", "MA5-3MG", "MA5-4MG", "MA5-5MG", "MA5-6MG", "MA5-7MG", "MA5-1NA", "MA5-2NA", "MA5-3NA", "MA5-4NA", "MA5-1N", "MA5-2N", "MA5-3N", "MA5-4N", "MA5-5N", "MA5-6N", "MA5-7N", "MA5-1P", "MA5-2P", "MA5-3P", "MA5-4P", "MA5-5P", "MA5-6P", "MA5-7P"],
            "S6": ["MA-S1", "MA-S2", "MA-S3", "MA-S4", "MA-S5", "MA-S6", "MA-S7", "MA-S8", "MA-S9", "MA-S10", "MA-S11", "MA-S12"],
        },
        "content": {
            "S4": [
                "Number and Algebra: rational numbers, ratios, percentages, algebraic techniques, linear relationships",
                "Measurement and Geometry: area, volume, time, Pythagoras and trigonometry",
                "Statistics and Probability: data collection, analysis, probability",
            ],
            "S5": [
                "Number and Algebra: surds, indices, quadratics, simultaneous equations, inequalities",
                "Measurement and Geometry: trigonometry, mensuration, geometric properties",
                "Statistics and Probability: bivariate data, probability, statistical analysis",
            ],
            "S6": [
                "Core: Algebra, Functions, Calculus, Probability, Statistical Analysis",
                "Extension 1: Polynomials, Trigonometry, Calculus, Combinatorics",
                "Extension 2: Proof, Vectors, Complex Numbers, Mechanics, Statistics",
            ],
        },
    },
    "science": {
        "name": "Science",
        "code": "SC",
        "stages": {
            "ES1": ["ST1-1WS", "ST1-2WS", "ST1-3WS", "ST1-4WS", "ST1-5LW", "ST1-6LW", "ST1-7LW", "ST1-8ES", "ST1-9ES", "ST1-10ES", "ST1-11ES", "ST1-12CES"],
            "S1": ["ST1-1WS", "ST1-2WS", "ST1-3WS", "ST1-4WS", "ST1-5LW", "ST1-6LW", "ST1-7LW", "ST1-8ES", "ST1-9ES", "ST1-10ES", "ST1-11ES", "ST1-12CES"],
            "S2": ["ST2-1WS", "ST2-2WS", "ST2-3WS", "ST2-4WS", "ST2-5LW", "ST2-6LW", "ST2-7LW", "ST2-8ES", "ST2-9ES", "ST2-10ES", "ST2-11ES", "ST2-12CES"],
            "S3": ["ST3-1WS", "ST3-2WS", "ST3-3WS", "ST3-4WS", "ST3-5LW", "ST3-6LW", "ST3-7LW", "ST3-8ES", "ST3-9ES", "ST3-10ES", "ST3-11ES", "ST3-12CES"],
            "S4": ["ST4-1WS", "ST4-2WS", "ST4-3WS", "ST4-4WS", "ST4-5LW", "ST4-6LW", "ST4-7LW", "ST4-8ES", "ST4-9ES", "ST4-10ES", "ST4-11CES", "ST4-12CES"],
            "S5": ["ST5-1WS", "ST5-2WS", "ST5-3WS", "ST5-4WS", "ST5-5LW", "ST5-6LW", "ST5-7LW", "ST5-8ES", "ST5-9ES", "ST5-10ES", "ST5-11CES", "ST5-12CES"],
            "S6": ["ENS1-1", "ENS1-2", "ENS1-3", "ENS1-4", "ENS1-5", "ENS1-6", "ENS1-7", "ENS1-8"],
        },
        "content": {
            "S4": [
                "Working Scientifically: inquiry skills, safe work practices",
                "Living World: cells, body systems, reproduction, genetics",
                "Earth and Space: plate tectonics, rock cycle, atmosphere, solar system",
                "Physical World: forces, energy, waves, electricity, magnetism",
                "Chemical World: elements, compounds, mixtures, chemical reactions, atoms",
            ],
            "S5": [
                "Working Scientifically: advanced inquiry, data analysis, fieldwork",
                "Living World: biodiversity, ecosystems, disease, biotechnology",
                "Earth and Space: resources, climate, sustainable Earth, universe",
                "Physical World: motion, forces, energy transformations, waves, electricity",
                "Chemical World: periodic table, chemical reactions, rates, equilibrium",
            ],
            "S6": [
                "Biology: cells, genetics, biodiversity, ecosystems, evolution, human biology",
                "Chemistry: atomic structure, bonding, reactions, equilibrium, organic chemistry",
                "Physics: motion, forces, energy, waves, electricity, magnetism, nuclear physics",
                "Earth and Environmental Science: plate tectonics, cycles, climate, resources",
                "Investigating Science: inquiry skills, data analysis, experimental design",
            ],
        },
    },
    "history": {
        "name": "History",
        "code": "HH",
        "stages": {
            "S3": ["HH3-1", "HH3-2", "HH3-3", "HH3-4", "HH3-5", "HH3-6", "HH3-7", "HH3-8", "HH3-9"],
            "S4": ["HH4-1", "HH4-2", "HH4-3", "HH4-4", "HH4-5", "HH4-6", "HH4-7", "HH4-8", "HH4-9"],
            "S5": ["HH5-1", "HH5-2", "HH5-3", "HH5-4", "HH5-5", "HH5-6", "HH5-7", "HH5-8", "HH5-9"],
            "S6": ["HH11-1", "HH11-2", "HH11-3", "HH11-4", "HH11-5", "HH12-1", "HH12-2", "HH12-3", "HH12-4", "HH12-5"],
        },
        "content": {
            "S3": [
                "Aboriginal and Torres Strait Islander histories",
                "First fleet and colonial Australia",
                "Federation and nation building",
                "Migration and diversity in Australia",
            ],
            "S4": [
                "Ancient Rome, Greece, or Egypt",
                "Medieval Europe",
                "The Black Death and its impact",
                "Renaissance and Reformation",
            ],
            "S5": [
                "World War I",
                "World War II",
                "The Holocaust",
                "Rights and freedoms (civil rights)",
                "Australia in the Vietnam War era",
            ],
            "S6": [
                "Modern History: WWI, WWII, Cold War, globalisation",
                "Ancient History: archaeological methods, ancient societies",
                "History Extension: historiography, historical inquiry",
            ],
        },
    },
    "geography": {
        "name": "Geography",
        "code": "HG",
        "stages": {
            "S3": ["HG3-1", "HG3-2", "HG3-3", "HG3-4", "HG3-5", "HG3-6", "HG3-7", "HG3-8"],
            "S4": ["HG4-1", "HG4-2", "HG4-3", "HG4-4", "HG4-5", "HG4-6", "HG4-7", "HG4-8"],
            "S5": ["HG5-1", "HG5-2", "HG5-3", "HG5-4", "HG5-5", "HG5-6", "HG5-7", "HG5-8"],
            "S6": ["HG11-1", "HG11-2", "HG11-3", "HG11-4", "HG11-5", "HG12-1", "HG12-2", "HG12-3", "HG12-4", "HG12-5"],
        },
        "content": {
            "S4": [
                "Biomes and food security",
                "Changing places",
                "Environmental change and management",
                "Global interactions",
            ],
            "S5": [
                "Natural environments and human impacts",
                "Environmental change and management",
                "Global interconnections",
                "Migration and population",
            ],
            "S6": [
                "Earth's Environmental Systems",
                "Human Processes and Environmental Change",
                "Environmental Management and Sustainability",
                "Global Networks and Interdependence",
            ],
        },
    },
    "pdhpe": {
        "name": "Personal Development, Health and Physical Education",
        "code": "PD",
        "stages": {
            "ES1": ["PD1-1", "PD1-2", "PD1-3", "PD1-4", "PD1-5", "PD1-6", "PD1-7", "PD1-8", "PD1-9", "PD1-10"],
            "S1": ["PD1-1", "PD1-2", "PD1-3", "PD1-4", "PD1-5", "PD1-6", "PD1-7", "PD1-8", "PD1-9", "PD1-10"],
            "S2": ["PD2-1", "PD2-2", "PD2-3", "PD2-4", "PD2-5", "PD2-6", "PD2-7", "PD2-8", "PD2-9", "PD2-10"],
            "S3": ["PD3-1", "PD3-2", "PD3-3", "PD3-4", "PD3-5", "PD3-6", "PD3-7", "PD3-8", "PD3-9", "PD3-10"],
            "S4": ["PD4-1", "PD4-2", "PD4-3", "PD4-4", "PD4-5", "PD4-6", "PD4-7", "PD4-8", "PD4-9", "PD4-10"],
            "S5": ["PD5-1", "PD5-2", "PD5-3", "PD5-4", "PD5-5", "PD5-6", "PD5-7", "PD5-8", "PD5-9", "PD5-10"],
            "S6": ["PD11-1", "PD11-2", "PD11-3", "PD11-4", "PD11-5", "PD12-1", "PD12-2", "PD12-3", "PD12-4", "PD12-5"],
        },
    },
    "technologies": {
        "name": "Technologies",
        "code": "TS",
        "stages": {
            "ES1": ["TS1-1", "TS1-2", "TS1-3", "TS1-4"],
            "S1": ["TS1-1", "TS1-2", "TS1-3", "TS1-4"],
            "S2": ["TS2-1", "TS2-2", "TS2-3", "TS2-4"],
            "S3": ["TS3-1", "TS3-2", "TS3-3", "TS3-4"],
            "S4": ["TS4-1", "TS4-2", "TS4-3", "TS4-4"],
            "S5": ["TS5-1", "TS5-2", "TS5-3", "TS5-4"],
            "S6": ["IT11-1", "IT11-2", "IT11-3", "IT11-4"],
        },
    },
    "creative_arts": {
        "name": "Creative Arts",
        "code": "CA",
        "stages": {
            "ES1": ["CA1-1", "CA1-2", "CA1-3", "CA1-4", "CA1-5"],
            "S1": ["CA1-1", "CA1-2", "CA1-3", "CA1-4", "CA1-5"],
            "S2": ["CA2-1", "CA2-2", "CA2-3", "CA2-4", "CA2-5"],
            "S3": ["CA3-1", "CA3-2", "CA3-3", "CA3-4", "CA3-5"],
        },
    },
    "languages": {
        "name": "Languages",
        "code": "LA",
        "stages": {
            "ES1": ["LA1-1", "LA1-2"],
            "S1": ["LA1-1", "LA1-2"],
            "S2": ["LA2-1", "LA2-2"],
            "S3": ["LA3-1", "LA3-2"],
            "S4": ["LA4-1", "LA4-2"],
            "S5": ["LA5-1", "LA5-2"],
            "S6": ["LA11-1", "LA11-2"],
        },
    },
    "aboriginal": {
        "name": "Aboriginal and Torres Strait Islander Histories and Cultures",
        "code": "AI",
        "stages": {
            "ES1": ["AI1-1"],
            "S1": ["AI1-1"],
            "S2": ["AI2-1"],
            "S3": ["AI3-1"],
            "S4": ["AI4-1"],
            "S5": ["AI5-1"],
            "S6": ["AI11-1"],
        },
    },
}

# HSC Subject List (NSW Stage 6)
HSC_SUBJECTS = {
    "6101": {"name": "Aboriginal Studies", "category": "Board Developed"},
    "6102": {"name": "Agriculture", "category": "Board Developed"},
    "6103": {"name": "Ancient History", "category": "Board Developed"},
    "6104": {"name": "Business Studies", "category": "Board Developed"},
    "6105": {"name": "Chemistry", "category": "Board Developed"},
    "6106": {"name": "Community and Family Studies", "category": "Board Developed"},
    "6107": {"name": "Drama", "category": "Board Developed"},
    "6108": {"name": "Earth and Environmental Science", "category": "Board Developed"},
    "6109": {"name": "Economics", "category": "Board Developed"},
    "6110": {"name": "Engineering Studies", "category": "Board Developed"},
    "6111": {"name": "English Advanced", "category": "Board Developed"},
    "6112": {"name": "English Standard", "category": "Board Developed"},
    "6113": {"name": "English Extension 1", "category": "Board Developed"},
    "6114": {"name": "English Extension 2", "category": "Board Developed"},
    "6115": {"name": "Food Technology", "category": "Board Developed"},
    "6116": {"name": "Geography", "category": "Board Developed"},
    "6117": {"name": "Information Processes and Technology", "category": "Board Developed"},
    "6118": {"name": "Investigating Science", "category": "Board Developed"},
    "6119": {"name": "Legal Studies", "category": "Board Developed"},
    "6120": {"name": "Mathematics Advanced", "category": "Board Developed"},
    "6121": {"name": "Mathematics Extension 1", "category": "Board Developed"},
    "6122": {"name": "Mathematics Extension 2", "category": "Board Developed"},
    "6123": {"name": "Modern History", "category": "Board Developed"},
    "6124": {"name": "Music", "category": "Board Developed"},
    "6125": {"name": "Physics", "category": "Board Developed"},
    "6126": {"name": "Psychology", "category": "Board Developed"},
    "6127": {"name": "Senior Science", "category": "Board Developed"},
    "6128": {"name": "Society and Culture", "category": "Board Developed"},
    "6129": {"name": "Software Development", "category": "Board Developed"},
    "6130": {"name": "Studies of Religion", "category": "Board Developed"},
    "6131": {"name": "Textiles and Design", "category": "Board Developed"},
    "6132": {"name": "Visual Arts", "category": "Board Developed"},
    "6133": {"name": "Visual Design", "category": "Board Developed"},
}

# General capabilities from the NSW curriculum
GENERAL_CAPABILITIES = [
    "Literacy", "Numeracy", "ICT Capability", "Critical and Creative Thinking",
    "Personal and Social Capability", "Ethical Understanding", "Intercultural Understanding",
]

# Cross-curriculum priorities
PRIORITY_AREAS = [
    "Aboriginal and Torres Strait Islander Histories and Cultures",
    "Asia and Australia's Engagement with Asia",
    "Sustainability",
]


class NSWCurriculumService:

    def get_stages(self) -> dict:
        return NSW_STAGES

    def get_klas(self) -> dict:
        return {k: {"name": v["name"], "code": v["code"]} for k, v in NSW_KLAS.items()}

    def get_subject_content(self, kla: str, stage: str) -> list[str]:
        """Get content descriptors for a subject at a stage."""
        kla_data = NSW_KLAS.get(kla.lower())
        if not kla_data:
            return []
        return kla_data.get("content", {}).get(stage, [])

    def get_outcomes(self, kla: str, stage: str) -> list[str]:
        """Get curriculum outcomes for a subject at a stage."""
        kla_data = NSW_KLAS.get(kla.lower())
        if not kla_data:
            return []
        return kla_data.get("stages", {}).get(stage, [])

    def get_hsc_subjects(self) -> dict:
        return HSC_SUBJECTS

    def get_stage_for_age(self, age: int) -> str | None:
        """Map an age to a NSW stage."""
        if age <= 5:
            return "ES1"
        elif age <= 7:
            return "S1"
        elif age <= 9:
            return "S2"
        elif age <= 11:
            return "S3"
        elif age <= 14:
            return "S4"
        elif age <= 16:
            return "S5"
        elif age <= 18:
            return "S6"
        return None

    def get_general_capabilities(self) -> list[str]:
        return GENERAL_CAPABILITIES

    def get_priority_areas(self) -> list[str]:
        return PRIORITY_AREAS

    def search_curriculum(self, query: str) -> list[dict]:
        """Search curriculum content across all KLAs and stages."""
        q = query.lower()
        results = []
        for kla_key, kla_data in NSW_KLAS.items():
            for stage, content_list in kla_data.get("content", {}).items():
                for content in content_list:
                    if q in content.lower():
                        results.append({
                            "kla": kla_data["name"],
                            "stage": stage,
                            "content": content,
                            "outcomes": kla_data["stages"].get(stage, []),
                        })
        return results

    def get_learning_progression(self, kla: str) -> dict:
        """Show how a subject progresses across stages."""
        kла_data = NSW_KLAS.get(kla.lower())
        if not kла_data:
            return {}
        progression = {}
        for stage in ["ES1", "S1", "S2", "S3", "S4", "S5", "S6"]:
            content = kла_data.get("content", {}).get(stage, [])
            outcomes = kла_data.get("stages", {}).get(stage, [])
            if content or outcomes:
                progression[stage] = {
                    "stage_name": NSW_STAGES[stage]["name"],
                    "content": content,
                    "outcomes": outcomes,
                }
        return progression


def get_curriculum_service() -> NSWCurriculumService:
    return NSWCurriculumService()
