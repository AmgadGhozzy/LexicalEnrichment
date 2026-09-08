import sqlite3

def apply_final_category_mapping(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    LEX_TO_APP_CATEGORY = {
        "Food & Drink": "Food & Drink", "Consumption": "Food & Drink", "Substance": "Food & Drink",
        "Body": "Health & Senses", "Health & Body": "Health & Senses", "Perception": "Health & Senses",
        "Emotion": "Feelings & Emotions", "Emotions": "Feelings & Emotions", 
        "Feeling": "Feelings & Emotions", "Motive": "Feelings & Emotions",
        "Places & Travel": "Travel & Movement", "Motion": "Travel & Movement", "Location": "Travel & Movement",
        "Objects & Tools": "Objects & Tools", "Object": "Objects & Tools", "Artifact": "Objects & Tools",
        "Social": "Social Life & Communication", "Society": "Social Life & Communication", 
        "Communication": "Social Life & Communication", "Competition": "Social Life & Communication",
        "Mind & Thinking": "Mind & Thinking", "Cognition": "Mind & Thinking", "Knowledge": "Mind & Thinking",
        "Math & Numbers": "Numbers, Time & Math", "Quantity": "Numbers, Time & Math", 
        "Time": "Numbers, Time & Math", "Shape": "Numbers, Time & Math",
        "Animals": "Nature & Science", "Plant": "Nature & Science", "Phenomenon": "Nature & Science",
        "Actions": "Actions & Processes", "Process": "Actions & Processes", 
        "Change": "Actions & Processes", "Contact": "Actions & Processes",
        "General": "General / Common", "General Quality": "General / Common", 
        "Attribute": "General / Common", "Tops": "General / Common", "Pert": "General / Common"
    }

    print("🛠 Applying Final User-Friendly Categories...")

    # 1. تحديث الفئات القديمة إلى الجديدة
    for old_cat, new_cat in LEX_TO_APP_CATEGORY.items():
        cursor.execute("UPDATE wordsMaster SET category = ? WHERE category = ?", (new_cat, old_cat))

    # 2. معالجة الفئات التي لم تشملها القائمة (التنظيف النهائي)
    # نحتاج لتوليد علامات استفهام ديناميكية بعدد الفئات الجديدة
    unique_new_categories = list(set(LEX_TO_APP_CATEGORY.values()))
    placeholders = ', '.join(['?'] * len(unique_new_categories))
    
    query = f"UPDATE wordsMaster SET category = 'General / Common' WHERE category NOT IN ({placeholders}) OR category IS NULL"
    
    cursor.execute(query, unique_new_categories)

    conn.commit()
    conn.close()
    print("✅ Categories Standardized Successfully!")

# لتشغيل الكود:
apply_final_category_mapping('/storage/emulated/0/DictionaryEnrichment/WordsMaster.db')