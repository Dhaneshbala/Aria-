"""
NSW Curriculum (NESA) — Stage 4 & 5 syllabus content for worksheet generation.
Aligned to the NSW Education Standards Authority syllabuses.
"""

NSW_STAGES = {
    "Stage 4": {"years": "7-8", "age": "12-14"},
    "Stage 5": {"years": "9-10", "age": "14-16"},
}

# ── English (EN4) ────────────────────────────────────────────────────────────

NSW_ENGLISH = {
    "Stage 4": {
        "outcomes": [
            "EN4-1A — responds to and composes texts for understanding, interpretation, critical analysis, imaginative expression and pleasure",
            "EN4-2A — plans, comiles and revises for publication a range of textual outcomes, using knowledge of purpose, audience and subject matter",
            "EN4-3D — uses and describes the English language and its patterns, rules and conventions deliberately and effectively in different contexts",
            "EN4-4E — thinks critically and interpretively about texts, responding to and evaluating their relationships with their context and other texts",
            "EN4-5F — recognises, reflects on and assesses their capacity to interpret texts, compose texts and speak in a variety of situations",
        ],
        "modules": [
            "Early Modern Texts", "Imaginative Writing", "Persuasive Writing",
            "Poetry", "Film Study", "Media Literacy", "Spoken Text",
        ],
        "topics": [
            "Essay writing (introduction, body, conclusion, thesis statement, topic sentences)",
            "Creative writing (narrative techniques, characterisation, setting, dialogue, plot structure)",
            "Persuasive text analysis (techniques, arguments, counter-arguments, rhetorical questions)",
            "Poetry analysis (figurative language, imagery, structure, tone, theme)",
            "Film study (camera techniques, sound, mise-en-scene, narrative conventions)",
            "Informative and explanatory writing (textual features, structure, cohesion)",
            "Grammar and punctuation (sentence types, punctuation marks, clause structure)",
            "Visual literacy (advertisements, posters, digital media, multimodal texts)",
            "Comparison of texts (similarities, differences, context, purpose, audience)",
            "Speaking and listening (formal presentations, group discussions, active listening)",
        ],
    },
    "Stage 5": {
        "outcomes": [
            "EN5-1A — thinks critically and analytically to evaluate texts and compose clear and effective texts for a range of purposes and audiences",
            "EN5-2A — selects and uses a variety of language features, textual structures and conventions appropriately for a range of purposes and audiences",
            "EN5-3D — thinks critically and interpretively about texts, considering context, purpose, audience and form",
            "EN5-4E — reflects on and evaluates their own and others' texts to improve their own composing, reading and viewing",
            "EN5-5F — uses a range of technologies appropriately to compose, publish and reflect on texts",
        ],
        "modules": [
            "Extended Writing", "Critical Study of Literature", "Media Representation",
            "Multimodal Texts", "Public Speaking", "Creative Non-fiction",
        ],
        "topics": [
            "Discursive essays (balanced arguments, evidence, synthesis)",
            "Analytical essays (thesis development, evidence integration, paragraph structure)",
            "Narrative writing (complex structures, unreliable narrators, symbolism)",
            "Persuasive speeches (ethos, pathos, logos, call to action)",
            "Critical study of a novel (themes, characters, context, author's purpose)",
            "Short story analysis (irony, allegory, narrative voice)",
            "Media analysis (bias, representation, framing, language features)",
            "Year 11-12 English preparation (close reading, critical thinking, academic writing)",
        ],
    },
}

# ── Mathematics (MA4-5) ─────────────────────────────────────────────────────

NSW_MATHS = {
    "Stage 4": {
        "outcomes": [
            "MA4-1NA — applies number properties and operations, including a large range of mental techniques, in solving problems, and in counting",
            "MA4-2NA — operates with ratios and rates, and in solving problems involving percentage change, including percentage increase and decrease",
            "MA4-3WM — uses and interprets formal mathematical language to describe and communicate mathematical ideas",
            "MA4-4NA — solves and models a range of practical situations, using appropriate mathematical knowledge and techniques",
            "MA4-5NA — uses algebraic techniques to solve a range of mathematical problems, including those involving financial maths",
            "MA4-6NA — uses and applies measurement skills to solve problems, and in calculating area and volume of a wide range of shapes",
            "MA4-7NA — identifies and uses congruence and similarity, and applies angle properties to solve problems",
            "MA4-8NA — locates and describes position on a Cartesian plane, and in transforming plane figures",
            "MA4-9NA — uses the statistical investigation process to answer questions arising from a mixture of data sources",
            "MA4-10NA — uses and applies the statistical process to investigate questions involving two variables",
            "MA4-11NA — analyses and represents financial data and solves a range of authentic problems",
        ],
        "topics": [
            "Number: integers, fractions, decimals, percentages, ratios, rates, scientific notation",
            "Algebra: algebraic expressions, equations, inequalities, patterns, linear relationships",
            "Measurement: perimeter, area, volume, surface area, units, time, money",
            "Geometry: angle properties, triangles, quadrilaterals, congruence, transformations, coordinate geometry",
            "Statistics: data collection, surveys, statistical measures (mean, median, mode, range), data displays",
            "Probability: probability scale, tree diagrams, two-way tables, experimental vs theoretical probability",
            "Financial maths: GST, discounts, profit/loss, interest, budgeting",
        ],
    },
    "Stage 5": {
        "outcomes": [
            "MA5.1-1NA — operates with ratio and rate, and applies these to solve problems involving percentage change",
            "MA5.1-2NA — solves problems involving simple and compound interest",
            "MA5.1-3WM — uses and interprets formal mathematical language",
            "MA5.2-1NA — uses algebraic techniques to solve a range of mathematical problems",
            "MA5.2-2NA — operates with surds and indices, and uses the logarithmic scale",
            "MA5.2-3WM — applies mathematical thinking to describe and model situations",
            "MA5.2-4NA — models and solves numerically, algebraically and graphically a range of practical problems involving linear equations, inequalities and non-linear relationships",
            "MA5.3-1NA — uses and applies algebraic techniques to solve a range of mathematical problems",
            "MA5.3-2NA — operates with surds and indices and uses the logarithmic scale",
            "MA5.3-3WM — applies and justifies the use of geometric and statistical reasoning",
        ],
        "topics": [
            "Algebra: quadratics, simultaneous equations, inequalities, non-linear relationships",
            "Geometry: circle theorems, trigonometry (sine, cosine, tangent rules), Pythagoras' theorem",
            "Measurement: volume and surface area of cylinders, prisms, composite solids",
            "Statistics: box plots, scatter plots, lines of best fit, correlation, two-way tables",
            "Probability: conditional probability, Venn diagrams, independent events",
            "Financial maths: compound interest, depreciation, inflation, loan repayments",
            "Indices and surds: index laws, scientific notation, rational/irrational numbers",
            "Linear and non-linear relationships: gradient, equation of a line, parabolas, exponential functions",
        ],
    },
}

# ── Science (Sc4-5) ─────────────────────────────────────────────────────────

NSW_SCIENCE = {
    "Stage 4": {
        "outcomes": [
            "SC4-1WS — plans and conducts scientific investigations to test hypotheses, collecting and analysing data using appropriate technologies",
            "SC4-4LW — describes some physical conditions which can change the growth and survival of living things",
            "SC4-5LW — describes the structure and function of cells and multicellular organisms",
            "SC4-6LW — describes how organisms are adapted to their environment",
            "SC4-7CW — describes the dynamic nature of models and theories about the particle model of matter",
            "SC4-8LW — explains how food provides the energy and matter needed by organisms for growth and survival",
            "SC4-9LW — describes some human impacts on environments and the strategies that can be used to reduce these impacts",
            "SC4-10LW — describes how advances in technology have affected scientific understanding",
            "SC4-11ES — explains the dynamic nature of the Earth's surface through the concept of plate tectonics",
            "SC4-12ES — describes the processes that contribute to the changing of the Earth's surface over time",
            "SC4-13PD — identifies the effects of personal and peer decisions on health and well-being",
            "SC4-14PD — plans and conducts investigations to measure physical fitness components",
            "SC4-15IC — uses scientific understanding and skills in familiar and new situations",
        ],
        "topics": [
            "Cells and cell division", "Digestive system", "Circulatory and respiratory systems",
            "Ecosystems and food webs", "Adaptations and natural selection", "Genetics and inheritance",
            "States of matter", "Atoms and elements", "Chemical reactions", "Mixtures and solutions",
            "Forces and motion", "Energy transformations", "Electrical circuits",
            "Plate tectonics", "Weathering and erosion", "Rock cycle", "Earth's atmosphere",
            "Human impact on the environment", "Water cycle and sustainability",
        ],
    },
    "Stage 5": {
        "outcomes": [
            "SC5-1WS — plans and conducts scientific investigations to test hypotheses, collecting and analysing data",
            "SC5-4LW — analyses the transfer of matter and energy in living systems",
            "SC5-5LW — explains the role of evolution in producing diversity of life",
            "SC5-6LW — analyses the effects of human and environmental factors on cell function",
            "SC5-7CW — uses models to explain properties of matter at the particulate level",
            "SC5-8LW — analyses the effects of chemical reactions in terms of energy and reactants/products",
            "SC5-9LW — evaluates management strategies for maintaining or improving ecosystem sustainability",
            "SC5-10ES — uses the theory of plate tectonics to explain the features of the Earth",
            "SC5-11ES — describes the formation of the Earth's atmosphere over geological time",
            "SC5-12PD — analyses the effects of exercise and nutrition on the human body",
            "SC5-13PD — evaluates the impact of personal choices on community health and safety",
        ],
        "topics": [
            "Advanced cell biology", "DNA and protein synthesis", "Homeostasis",
            "Ecosystem dynamics", "Classification and phylogenetics", "Evolution and speciation",
            "Atomic structure", "Periodic table trends", "Chemical bonding",
            "Balancing equations", "Acids, bases, and pH", "Rate of reactions",
            "Wave physics", "Energy and momentum", "Electromagnetic spectrum",
            "Earth's geological history", "Fossil fuels and renewable energy",
            "Climate change science", "Nanotechnology and materials science",
        ],
    },
}

# ── HSIE / Geography / History ──────────────────────────────────────────────

NSW_HSIE = {
    "Stage 4": {
        "topics": [
            # Geography
            "Factors affecting food and water security", "Environmental change and management",
            "Interconnections between places", "Global megacities", "Natural hazards",
            # History
            "The Ancient World (Rome, Greece, Egypt, China)", "Medieval Europe",
            "The Black Death", "The Renaissance", "Contact and conquest (1770-1810)",
            "Colonial Australia", "The Industrial Revolution",
        ],
    },
    "Stage 5": {
        "topics": [
            # Geography
            "Human-environment interactions", "Water in the world", "Environmental change",
            "Global spatial inequalities", "Changing places, changing people",
            # History
            "Australia in the 20th century (WWI, WWII, the Depression)",
            "Rights and freedoms", "Migration to Australia",
            "The Cold War", "The Vietnam War", "Australia in Asia",
            "Aboriginal civil rights movement", "The environment movement",
        ],
    },
}

# ── PDHPE ────────────────────────────────────────────────────────────────────

NSW_PDHPE = {
    "Stage 4": {
        "topics": [
            "Personal identity and self-awareness", "Healthy eating and nutrition",
            "Physical activity and fitness", "Mental health and well-being",
            "Safety and risk management", "Peer relationships and communication",
            "Growth and development", "Substances and their effects",
            "Diversity and inclusion", "Personal health management",
        ],
    },
    "Stage 5": {
        "topics": [
            "Nutrition for performance", "Cardiovascular and muscular fitness",
            "Mental health strategies", "Body image and media influence",
            "Substance use prevention", "Healthy relationships",
            "First aid and emergency response", "Community health and safety",
            "Social and environmental influences on health",
        ],
    },
}

# ── Technology (TAS) ────────────────────────────────────────────────────────

NSW_TECH = {
    "Stage 4": {
        "topics": [
            "Design process", "Engineering principles", "Food technology basics",
            "Timber and metal technologies", "Textiles and materials",
            "Digital technologies and coding basics", "Graphics and CAD",
            "Sustainability in design", "Systems thinking",
        ],
    },
    "Stage 5": {
        "topics": [
            "Advanced CAD and prototyping", "Robotics and automation",
            "Food science and processing", "Industrial design",
            "Software development basics", "Electronics and circuits",
            "Engineering structures", "Biotechnology applications",
            "Sustainable product design",
        ],
    },
}

# ── Creative Arts (Visual Arts, Music, Drama) ──────────────────────────────

NSW_ARTS = {
    "Stage 4": {
        "topics": [
            # Visual Arts
            "Elements of art (line, shape, colour, form, texture, space)",
            "Principles of design (balance, contrast, emphasis, pattern, unity)",
            "Australian Aboriginal art", "Art movements and styles",
            # Music
            "Elements of music (rhythm, melody, harmony, dynamics, texture)",
            "Music notation basics", "Ensemble performance",
            # Drama
            "Drama conventions (role, status, space, time, tension)",
            "Performance techniques", "Script writing basics",
        ],
    },
    "Stage 5": {
        "topics": [
            "Art criticism and aesthetics", "Contemporary art practices",
            "Photography and digital media", "Ceramics and sculpture",
            "Music composition and arrangement", "Music technology and production",
            "Improvisation and devised theatre", "Film making basics",
            "Cultural and historical art contexts",
        ],
    },
}

# ── Subject → curriculum mapping ────────────────────────────────────────────

SUBJECT_CURRICULUM = {
    "English": NSW_ENGLISH,
    "Mathematics": NSW_MATHS,
    "Science": NSW_SCIENCE,
    "HSIE": NSW_HSIE,
    "Geography": NSW_HSIE,
    "History": NSW_HSIE,
    "PDHPE": NSW_PDHPE,
    "PE & Health": NSW_PDHPE,
    "Technology": NSW_TECH,
    "Visual Arts": NSW_ARTS,
    "Music": NSW_ARTS,
    "Drama": NSW_ARTS,
}


def get_curriculum_context(subject: str, stage: str = "Stage 4", topic: str = "") -> str:
    """Build curriculum context string for worksheet generation prompts."""
    curriculum = SUBJECT_CURRICULUM.get(subject, {})
    stage_data = curriculum.get(stage, {})

    lines = [f"NSW {stage} ({NSW_STAGES.get(stage, {}).get('years', '?-?')} years, age {NSW_STAGES.get(stage, {}).get('age', '?-?')}):"]

    if "outcomes" in stage_data:
        lines.append("Syllabus outcomes:")
        for o in stage_data["outcomes"][:6]:
            lines.append(f"  - {o}")

    if "modules" in stage_data:
        lines.append(f"Modules: {', '.join(stage_data['modules'])}")

    if "topics" in stage_data:
        # Find most relevant topics based on the worksheet topic
        all_topics = stage_data["topics"]
        if topic:
            topic_lower = topic.lower()
            relevant = [t for t in all_topics if any(w in t.lower() for w in topic_lower.split())]
            if relevant:
                lines.append(f"Relevant topics: {', '.join(relevant[:5])}")
        lines.append(f"All topics: {', '.join(all_topics)}")

    return "\n".join(lines)


def detect_stage(grade: str) -> str:
    """Detect NSW stage from grade string."""
    grade_lower = grade.lower()
    if any(x in grade_lower for x in ["year 9", "year 10", "9", "10", "stage 5"]):
        return "Stage 5"
    return "Stage 4"
