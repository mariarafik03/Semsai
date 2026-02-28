import re

LOCATION_ALIASES = {
    # Cairo areas
    "tagmo3": "New Cairo",
    "tagamoa": "New Cairo",
    "el tagamoa": "New Cairo",
    "التجمع": "New Cairo",
    "new cairo": "New Cairo",
    "maadi": "Maadi",
    "المعادي": "Maadi",
    "zamalek": "Zamalek",
    "الزمالك": "Zamalek",
    "heliopolis": "Heliopolis",
    "masr el gedida": "Heliopolis",
    "مصر الجديدة": "Heliopolis",
    "nasr city": "Nasr City",
    "مدينة نصر": "Nasr City",
    "nasser city": "Nasr City",
    "dokki": "Dokki",
    "الدقي": "Dokki",
    "mohandeseen": "Mohandeseen",
    "mohandes": "Mohandeseen",
    "المهندسين": "Mohandeseen",
    "agouza": "Agouza",
    "العجوزة": "Agouza",
    "shubra": "Shubra",
    "شبرا": "Shubra",
    "ain shams": "Ain Shams",
    "عين شمس": "Ain Shams",
    "rehab": "Al Rehab",
    "الرحاب": "Al Rehab",
    "el rehab": "Al Rehab",
    "rehab city": "Al Rehab",
    "shorouk": "El Shorouk",
    "el shorouk": "El Shorouk",
    "الشروق": "El Shorouk",
    "badr": "Badr City",
    "مدينة بدر": "Badr City",
    "downtown": "Downtown Cairo",
    "wust el balad": "Downtown Cairo",
    "وسط البلد": "Downtown Cairo",
    "garden city": "Garden City",
    "جاردن سيتي": "Garden City",
    "katameya": "Katameya",
    "القطامية": "Katameya",
    "5th settlement": "5th Settlement",
    "el teseen": "5th Settlement",
    "التسعين": "5th Settlement",
    "obour": "El Obour",
    "العبور": "El Obour",
    "mostorod": "Mostorod",
    "cairo festival": "New Cairo",  # landmark-based
    "sodic": "New Cairo",

    # Giza areas
    "october": "6th of October",
    "6 october": "6th of October",
    "6th october": "6th of October",
    "6 of october": "6th of October",
    "سادس اكتوبر": "6th of October",
    "٦ اكتوبر": "6th of October",
    "haram": "Al Haram",
    "الهرم": "Al Haram",
    "pyramids": "Al Haram",
    "giza": "Giza",
    "الجيزة": "Giza",
    "faisal": "Faisal",
    "فيصل": "Faisal",
    "imbaba": "Imbaba",
    "إمبابة": "Imbaba",
    "boulak dakrour": "Boulak Dakrour",
    "بولاق الدكرور": "Boulak Dakrour",
    "sheikh zayed": "Sheikh Zayed",
    "الشيخ زايد": "Sheikh Zayed",
    "zayed": "Sheikh Zayed",
    "smart village": "Smart Village",
    "القرية الذكية": "Smart Village",
    "hadayek october": "6th of October",
    "حدائق اكتوبر": "6th of October",

    # North Coast
    "north coast": "North Coast",
    "sahel": "North Coast",
    "الساحل": "North Coast",
    "sidi abd el rahman": "Sidi Abd El Rahman",
    "سيدي عبد الرحمن": "Sidi Abd El Rahman",
    "marina": "Marina",
    "مارينا": "Marina",
    "alamein": "El Alamein",
    "el alamein": "El Alamein",
    "العلمين": "El Alamein",
    "new alamein": "New Alamein",
    "العلمين الجديدة": "New Alamein",
    "hacienda": "Hacienda Bay",
    "hacienda bay": "Hacienda Bay",
    "ras el hekma": "Ras El Hekma",
    "رأس الحكمة": "Ras El Hekma",
    "marassi": "Marassi",
    "مراسي": "Marassi",
    "amwaj": "Amwaj",
    "أمواج": "Amwaj",
    "diplo": "Diplo",
    "porto marina": "Porto Marina",
}


def normalize_location(user_input: str) -> str | None:
    """
    Normalize a user-provided location string to a standard city/area name.
    
    Args:
        user_input: Raw location string from user (Arabic or English)
    
    Returns:
        Normalized location name, or None if not recognized
    """
    if not user_input:
        return None

    # Clean: lowercase, strip extra spaces, remove punctuation
    cleaned = user_input.strip().lower()
    cleaned = re.sub(r'[،,.\-_]+', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Direct lookup
    if cleaned in LOCATION_ALIASES:
        return LOCATION_ALIASES[cleaned]

    # Partial match — check if any alias is contained in the input or vice versa
    for alias, normalized in LOCATION_ALIASES.items():
        if alias in cleaned or cleaned in alias:
            return normalized

    return None  # unrecognized location