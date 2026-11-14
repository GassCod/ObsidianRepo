#!/usr/bin/env python3
"""
Automated School Organizer & Table of Contents Generator for Obsidian.
Scans School/ directories, organizes notes into topic folders (Class work / Home work),
and automatically maintains consistent, elegant Tables of Contents with concise descriptions.
"""

import os
import sys
import json
import re
import shutil

class LZString:
    keyStrBase64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="

    @classmethod
    def decompressFromBase64(cls, input_str):
        if not input_str:
            return None
        clean_input = "".join([c for c in input_str if c in cls.keyStrBase64])
        return cls._decompress(len(clean_input), 32, lambda idx: cls.keyStrBase64.index(clean_input[idx]))

    @classmethod
    def _decompress(cls, length, resetValue, getNextValue):
        dictionary = [0, 1, 2]
        enlargeIn = 4
        numBits = 3
        result = []
        data_val = getNextValue(0)
        data_position = resetValue
        data_index = 1

        def read_bits(maxpower):
            nonlocal data_val, data_position, data_index
            bits = 0
            power = 1
            while power != maxpower:
                res = data_val & data_position
                data_position >>= 1
                if data_position == 0:
                    data_position = resetValue
                    data_val = getNextValue(data_index)
                    data_index += 1
                bits |= (power if res > 0 else 0)
                power <<= 1
            return bits

        bits = read_bits(4)
        c = bits
        if c == 0: c = read_bits(256)
        elif c == 1: c = read_bits(65536)
        elif c == 2: return ""

        dictionary.append(chr(c))
        w = chr(c)
        result.append(w)

        while True:
            if data_index > length: return ""
            c = read_bits(1 << numBits)
            if c == 0:
                c = read_bits(256)
                dictionary.append(chr(c))
                c = len(dictionary) - 1
                enlargeIn -= 1
            elif c == 1:
                c = read_bits(65536)
                dictionary.append(chr(c))
                c = len(dictionary) - 1
                enlargeIn -= 1
            elif c == 2:
                return "".join(result)

            if enlargeIn == 0:
                enlargeIn = 1 << numBits
                numBits += 1

            if c < len(dictionary) and dictionary[c] is not None:
                entry = dictionary[c]
            else:
                if c == len(dictionary):
                    entry = w + w[0]
                else:
                    return None
            result.append(entry)
            dictionary.append(w + entry[0])
            enlargeIn -= 1
            w = entry

            if enlargeIn == 0:
                enlargeIn = 1 << numBits
                numBits += 1

def load_excalidraw_text(filepath):
    """Extract plain text from Excalidraw or standard markdown."""
    try:
        with open(filepath, "r", errors="ignore") as fp:
            content = fp.read()
    except Exception:
        return ""
    
    extracted_texts = []
    
    # 1. Check markdown text outside drawing
    pre_drawing = content.split("## Drawing")[0]
    for line in pre_drawing.splitlines():
        line = line.strip()
        if not line or line.startswith("---") or line.startswith("#") or "Switch to EXCALIDRAW VIEW" in line or line.startswith("tags:") or line.startswith("excalidraw-plugin:"):
            continue
        extracted_texts.append(line)
        
    # 2. Decompress and read elements
    raw_json = None
    if "<<<<<<<" in content:
        lines = []
        skip = False
        for line in content.splitlines():
            if line.startswith("<<<<<<<"): continue
            elif line.startswith("======="): skip = True; continue
            elif line.startswith(">>>>>>>"): skip = False; continue
            if not skip: lines.append(line)
        content = "\n".join(lines)

    m = re.search(r"```compressed-json\n([\s\S]*?)```", content)
    if m:
        decomp = LZString.decompressFromBase64(m.group(1))
        if decomp:
            try: raw_json = json.loads(decomp)
            except Exception: pass
    if not raw_json:
        m2 = re.search(r"```json\n([\s\S]*?)```", content)
        if m2:
            try: raw_json = json.loads(m2.group(1))
            except Exception: pass
            
    if raw_json and "elements" in raw_json:
        for el in raw_json["elements"]:
            if el.get("isDeleted"): continue
            if el.get("type") == "text" and el.get("text", "").strip():
                extracted_texts.append(el["text"].strip())
                
    return " ".join(extracted_texts)

# Topic display names for markdown callouts
TOPIC_DISPLAY_NAMES = {
    "Sidra Andasit": "Sidra Andasit",
    "Istabrut": "Istabrut",
    "Cohot": "Cohot (Силы и законы Ньютона)",
    "Hok Huk": "Hok Huk (Закон Гука и упругость)",
    "Piruk vector": "Piruk vector (Разложение векторов)",
    "Вишнёвый сад": "Вишнёвый сад (А.П. Чехов)",
    "Герой нашего времени": "Герой нашего времени (М.Ю. Лермонтов)",
    "Полотенце с петухом": "Полотенце с петухом (М.А. Булгаков)",
    "Русский язык": "Русский язык и культура речи",
    "Mr. Know-All": 'Literature: "Mr. Know-All" (W. Somerset Maugham)',
    "Vocabulary & Reading": "Reading Comprehension & Vocabulary",
    "האדונית והרוכל": 'האדונית והרוכל (ש"י עגנון)',
    "צמיחת הלאומיות באירופה": "צמיחת הלאומיות באירופה (Национализм в Европе XIX века)",
    "הסדר החדש באירופה": "הסדר החדש באירופה (Нацистский «новый порядок» в Европе)",
    "אוצר מילים והבנת הנקרא": "אוצר מילים והבנת הנקרא",
    "ספר בראשית": "ספר בראשית (פרשת לך-לך)"
}

# Preferred topic ordering per subject
TOPIC_ORDER = {
    "Math": ["Sidra Andasit", "Istabrut"],
    "Phisics": ["Cohot", "Hok Huk", "Piruk vector"],
    "Russian": ["Вишнёвый сад", "Герой нашего времени", "Полотенце с петухом", "Русский язык"],
    "English": ["Mr. Know-All", "Vocabulary & Reading"],
    "History": ["צמיחת הלאומיות באירופה", "הסדר החדש באירופה"],
    "Literature": ["האדונית והרוכל"],
    "Lashon": ["אוצר מילים והבנת הנקרא"],
    "Tanah": ["ספר בראשית"]
}

# Explicit homework pairings when names don't match exactly
KNOWN_PAIRS = {
    ("Math", "26.10.26"): "7.11.26",
    ("History", "9.11.26"): "History classroom homework",
}

# Known concise descriptions (1-2 sentences max)
KNOWN_DESCRIPTIONS = {
    # Math - Sidra Andasit
    "Sidra Andasit": "Сводная таблица формул геометрической прогрессии ($a_n$, $S_n$, свойства соседних членов, разделение на четные/нечетные и половины).",
    "20.10.26_Math": "Что такое סדרה הנדסית, базовая формула $a_n = a_1 \\cdot q^{n-1}$.",
    "21.10.26_Math_CW": "Рекуррентная форма прогрессии ($a_{n+1} = a_n \\cdot q$), доказательство постоянства $q$ через $\\frac{a_{n+1}}{a_n}$ и свойство $b^2 = a \\cdot c$.",
    "25.10.26_Math": "Сумма геометрической прогрессии ($S_n$): формулы $S_n = \\frac{a_1(q^n - 1)}{q - 1}$ и $S_n = \\frac{a_n q - a_1}{q - 1}$, нахождение параметров по сумме.",
    "26.10.26_Math": "Задачки по сумме сидры андасит.",
    "8.11.26_Math": "Сумма первой и последней половины в сидре андасит и сумма четных и нечетных элементов.",
    "9.11.26_Math": "Сумма первой и последней половины в сидре андасит и сумма четных и нечетных элементов (задачи 11 и 12 со страницы 32).",
    "21.10.26_Math_HW": "Домашняя работа на свойства и формулы геометрической прогрессии.",
    "7.11.26_Math_HW": "Домашняя работа по вычислению сумм геометрической прогрессии.",
    "7.11.26": "Домашняя работа по вычислению сумм геометрической прогрессии.",
    
    # Math - Istabrut
    "6.10.26_Math": "Дерево вероятностей (עץ הסתברות), многоступенчатые события и расчет условной вероятности по формуле Байеса.",
    "7.10.26_Math_CW": "Задачи на дерево вероятностей, нахождение неизвестной вероятности $p$ и задачи на шары разных цветов.",
    "7.10.26_Math_HW": "Задачи на дерево вероятностей и распределение исходов.",
    "HomeWorkSukkot": "Решение задач на вероятность с помощью двумерных таблиц (טבלה דו-ממדית), объединение и пересечение событий.",
    "Noshat Bernoli": "Формула Бернулли (נוסחת ברנולי) для повторных независимых испытаний и домашняя работа по ней.",
    "Istabrut bagrut homework lehagasha": "Домашняя работа на сдачу по подготовке к багруту по теории вероятностей (задачи на дерево и формулу Бернулли).",

    # Phisics - Cohot
    "Cohot 1": "Статическая сила трения ($f_{s\\max} = \\mu_s \\cdot N$) и сила трения в движении ($f_k = \\mu_k \\cdot N$).",
    "11.08.26_Phisics": "Системы подвижных и неподвижных блоков (גלגלות), второй закон Ньютона ($\\Sigma \\vec{F} = m\\vec{a}$) и равноускоренное движение.",
    "18-19.10.26_Phisics": "3-й закон Ньютона ($\\vec{F}_{1,2} = -\\vec{F}_{2,1}$) и равновесие подвешенного груза: расчет натяжения нитей ($T_1, T_2$).",
    "Cohot tasks": "Задачки по силам: расчет сил трения, натяжения нитей и условий равновесия тел.",
    "Phisics Bohan Sukkot prep": "Комплексная подготовка к контрольной работе (бохану): задачи на растяжение пружин, натяжение нитей и законы Ньютона.",

    # Phisics - Hok Huk
    "Hok Huk": "Закон Гука ($F_s = -k\\Delta x$) и сила тяжести ($W = mg$): схема растяжения пружины и расчет жесткости $k$.",
    "5.10.26_Phisics": "Экспериментальный график зависимости удлинения пружины от приложенной силы и нахождение жесткости пружины $k$.",

    # Phisics - Piruk vector
    "Piruk vektor": "Разложение векторов сил на координатные оси (פירוק וקטורים) и расчет проекций для нахождения равнодействующей силы.",

    # Russian
    "6.10.26_Russian": "Анализ персонажей Раневской, Гаева и Трофимова, а также символика сада и лопнувшей струны.",
    "5 Vishnevi Sad questions": "Ответы на вопросы по пьесе: продажа имения, конфликт уходящего дворянства и зарождающейся буржуазии в лице Лопахина.",
    "Герои Нашего Времени Багрут Вопросы": "Исторический контекст эпохи 1830-х годов: разгром декабристов, николаевская реакция, кризис идеалов и характеристика Печорина.",
    "Герои Нашего Времени Вопросы": "Анализ образа Печорина как «лишнего человека» эпохи реакции 1830-х годов и его взаимоотношений с другими героями романа.",
    "Полотенце с петухом вопросы": "Разбор рассказа из «Записок юного врача»: спасение покалеченной девушки, первая ампутация и символика вышитого полотенца.",
    "3.11.26_Russian": "Работа с текстом о стандартах красоты в обществе и практические упражнения на правописание частиц и приставок НЕ и НИ.",

    # Literature
    "28.10.26_Literature": "Композиционная структура рассказа (экспозиция, завязка, кульминация) и трансформация характера Йосефа от предприимчивого торговца к пассивной жертве.",
    "9.11.26_Literature": "Аллегорический смысл произведения: взаимоотношения европейского еврейства и антисемитского окружения накануне Катастрофы.",

    # English
    "11.08.26_English": "Анализ образа рассказчика и преодоления его предвзятого отношения к мистеру Келаде после эпизода с жемчужным ожерельем.",
    "3.11.26_English": "Аналитический раздел Bridging Text and Context: британские предрассудки эпохи и скрытые мотивы поведения мистера Келады.",
    "2.11.26_English": "Литературные приемы: концепция иронии на примере благородного поступка мистера Келады и олицетворение (personification).",
    "6.10.26_English": "Понимание прочитанного по теме мобильных приложений для изучения языков и отработка новой лексики (anticipate, persuade, mend).",
    "19.10.26_English": "Изучение фразовых глаголов (start out, turn down и др.) с подробными дефинициями и контекстными примерами.",
    "4.10.26_English": "Заметки к уроку английского языка.",

    # History
    "4.10.26_History": "Определение национализма, объединяющие нацию факторы (язык, культура, история) и последующие политические изменения в Европе.",
    "9.11.26_History": "Организация нацистского «нового порядка» в Европе: реализация расовой идеологии, экономическая эксплуатация и порабощение народов.",
    "History classroom homework": "Домашняя работа по теме нацистского «нового порядка» в Европе (характеристика расовой политики и оккупационного режима).",

    # Lashon
    "8.10.26_Lashon": "Разбор значений и контекстного употребления слов и выражений на иврите (שיטה, משוחחים, אי-קשר, לייעץ).",

    # Tanah
    "Tanah classroom work 20.10": "ספר בראשית פרק י\"ב (פרשת לך-לך): ציווי עזיבת המולדת, ההבטחה לאברם וירידתו למצרים בעקבות הרעב."
}

def determine_topic(subject, filename, text_content):
    """Identify topic based on subject, filename, and extracted text."""
    lower_text = text_content.lower()
    fname = filename.lower()
    
    if subject == "Math":
        if any(k in lower_text for k in ["סדרה הנדסית", "סדרה", "סידרה", "נוסחאות", "q=", "q =", "a_n", "a1", "an"]) or any(k in fname for k in ["sidra", "20.10", "21.10", "25.10", "26.10", "7.11", "8.11", "9.11"]):
            return "Sidra Andasit"
        return "Istabrut"
        
    elif subject == "Phisics":
        if any(k in lower_text for k in ["חוק הוק", "קפיץ", "hooke", "k="]) or "huk" in fname or "5.10" in fname:
            return "Hok Huk"
        elif any(k in lower_text for k in ["פירוק", "וקטור", "רכיבים", "vector"]) or "vektor" in fname:
            return "Piruk vector"
        return "Cohot"
        
    elif subject == "Russian":
        if any(k in lower_text for k in ["вишнев", "чехов", "раневск", "гаев", "лопахин", "трофимов"]) or "vishnevi" in fname or "6.10" in fname:
            return "Вишнёвый сад"
        elif any(k in lower_text for k in ["печорин", "лермонтов", "герои нашего", "декабрист", "грушницк"]) or "герои" in fname:
            return "Герой нашего времени"
        elif any(k in lower_text for k in ["полотенц", "булгаков", "доктор", "ампутац", "девушк"]) or "полотенце" in fname:
            return "Полотенце с петухом"
        return "Русский язык"
        
    elif subject == "Literature":
        return "האדונית והרוכל"
        
    elif subject == "English":
        if any(k in lower_text for k in ["kelada", "maugham", "know-all", "narrator", "pearl", "irony", "ramsay"]) or "11.08" in fname or "3.11" in fname or "2.11" in fname:
            return "Mr. Know-All"
        return "Vocabulary & Reading"
        
    elif subject == "History":
        if any(k in lower_text for k in ["סדר חדש", "אידיאולוגיה נאצית", "нацист", "новый порядок", "פולין", "שואה"]) or "9.11" in fname or "classroom homework" in fname:
            return "הסדר החדש באירופה"
        return "צמיחת הלאומיות באירופה"
        
    elif subject == "Lashon":
        return "אוצר מילים והבנת הנקרא"
        
    elif subject == "Tanah":
        return "ספר בראשית"
        
    return "Общее"

def get_description(subject, topic, base_name, work_type, text_content):
    """Retrieve curated description or generate a concise 1-2 sentence description."""
    key1 = f"{base_name}_{subject}_{'HW' if work_type == 'Home work' else 'CW'}"
    if key1 in KNOWN_DESCRIPTIONS:
        return KNOWN_DESCRIPTIONS[key1]
    key2 = f"{base_name}_{subject}"
    if key2 in KNOWN_DESCRIPTIONS:
        return KNOWN_DESCRIPTIONS[key2]
    if base_name in KNOWN_DESCRIPTIONS:
        return KNOWN_DESCRIPTIONS[base_name]
        
    # Auto-generate from note text if available
    if text_content and len(text_content.strip()) > 10:
        cleaned = re.sub(r"\s+", " ", text_content).strip()
        sentences = re.split(r"[.!?]\s+", cleaned)
        if sentences:
            desc = sentences[0].strip()
            if len(desc) < 30 and len(sentences) > 1:
                desc += ". " + sentences[1].strip()
            if not desc.endswith("."): desc += "."
            if len(desc) > 160:
                desc = desc[:157] + "..."
            return desc
            
    return f"Занятие по теме {topic} ({'домашняя работа' if work_type == 'Home work' else 'классная работа'})."

def organize_vault(vault_root="/home/petr/Documents/1/home"):
    school_dir = os.path.join(vault_root, "School")
    if not os.path.isdir(school_dir):
        print("School directory not found:", school_dir)
        return 0

    subjects = [d for d in os.listdir(school_dir) if os.path.isdir(os.path.join(school_dir, d)) and not d.startswith(".")]
    
    total_moved = 0

    # Explicit relocations for files currently in incorrect topic folders
    explicit_relocations = [
        # (subject, current_rel_path, target_topic, target_work_type)
        ("Math", "Istabrut/Home work/7.11.26.md", "Sidra Andasit", "Home work"),
        ("History", "צמיחת הלאומיות באירופה/Home work/History classroom homework.md", "הסדר החדש באירופה", "Home work"),
    ]

    for subj, cur_rel, tgt_topic, tgt_work in explicit_relocations:
        cur_full = os.path.join(school_dir, subj, cur_rel)
        if os.path.isfile(cur_full):
            tgt_dir = os.path.join(school_dir, subj, tgt_topic, tgt_work)
            os.makedirs(tgt_dir, exist_ok=True)
            fname = os.path.basename(cur_full)
            tgt_full = os.path.join(tgt_dir, fname)
            if cur_full != tgt_full:
                shutil.move(cur_full, tgt_full)
                print(f"[{subj}] Relocated {fname} -> {tgt_topic}/{tgt_work}/")
                total_moved += 1
    
    for subject in sorted(subjects):
        subj_dir = os.path.join(school_dir, subject)
        
        # 1. Gather all unorganized notes
        # Notes in School/<Subject>/Class work, School/<Subject>/Home work, or School/<Subject>/ directly
        files_to_process = []
        for root, dirs, files in os.walk(subj_dir):
            rel_from_subj = os.path.relpath(root, subj_dir)
            parts = rel_from_subj.split(os.sep) if rel_from_subj != "." else []
            
            for f in files:
                if not f.endswith(".md") or "table of content" in f.lower():
                    continue
                file_path = os.path.join(root, f)
                
                # Check if file is already organized into School/<Subject>/<Topic>/<WorkType>
                if len(parts) >= 2 and parts[1] in ["Class work", "Home work"]:
                    continue
                
                work_type = "Class work"
                if "home work" in file_path.lower():
                    work_type = "Home work"
                elif "cw" in f.lower():
                    work_type = "Class work"
                elif "hw" in f.lower() or "homework" in f.lower():
                    work_type = "Home work"
                    
                files_to_process.append((file_path, f, work_type))
                
        # 2. Move each unorganized file into its appropriate topic folder
        for file_path, fname, work_type in files_to_process:
            text = load_excalidraw_text(file_path)
            topic = determine_topic(subject, fname, text)
            
            target_dir = os.path.join(subj_dir, topic, work_type)
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, fname)
            
            if file_path != target_path:
                shutil.move(file_path, target_path)
                print(f"[{subject}] Moved {fname} -> {topic}/{work_type}/")
                total_moved += 1

        # 3. Clean up empty Class work / Home work directories directly under School/<Subject>
        for old_sub in ["Class work", "Home work"]:
            old_p = os.path.join(subj_dir, old_sub)
            if os.path.isdir(old_p) and not os.listdir(old_p):
                os.rmdir(old_p)

        # 4. Generate/Update Table of Content for this subject
        generate_table_of_content(subj_dir, subject)
        
    print(f"\nDone! Organized/updated files across School. Total moved: {total_moved}")
    return total_moved

def generate_table_of_content(subj_dir, subject):
    """Regenerate the Subject Table of Content.md with accurate links and descriptions."""
    topic_dirs = [d for d in os.listdir(subj_dir) if os.path.isdir(os.path.join(subj_dir, d)) and not d.startswith(".")]
    
    # Sort topics according to preferred order, then alphabetically
    pref_order = TOPIC_ORDER.get(subject, [])
    def topic_sort_key(t):
        if t in pref_order:
            return (0, pref_order.index(t))
        return (1, t)
    sorted_topics = sorted(topic_dirs, key=topic_sort_key)
    
    topic_data = {}
    for topic in sorted_topics:
        topic_path = os.path.join(subj_dir, topic)
        class_files = []
        home_files = []
        
        cw_dir = os.path.join(topic_path, "Class work")
        if os.path.isdir(cw_dir):
            for f in sorted(os.listdir(cw_dir)):
                if f.endswith(".md"): class_files.append((f, os.path.join(cw_dir, f)))
                
        hw_dir = os.path.join(topic_path, "Home work")
        if os.path.isdir(hw_dir):
            for f in sorted(os.listdir(hw_dir)):
                if f.endswith(".md"): home_files.append((f, os.path.join(hw_dir, f)))
                
        for f in sorted(os.listdir(topic_path)):
            if f.endswith(".md"):
                class_files.append((f, os.path.join(topic_path, f)))
                
        if class_files or home_files:
            topic_data[topic] = {"cw": class_files, "hw": home_files}
            
    toc_name = f"{subject} Table of Content.md"
    if subject.lower() == "phisics":
        toc_name = "Phisics table of content.md"
        
    toc_path = os.path.join(subj_dir, toc_name)
    lines = ["# 📚 Оглавление уроков\n"]
    
    # Priority foundational notes that should appear at the top of their topic
    TOP_PRIORITY_NOTES = {"Sidra Andasit", "Cohot 1", "Hok Huk", "Piruk vektor"}
    
    for topic in sorted_topics:
        if topic not in topic_data:
            continue
        data = topic_data[topic]
        
        display_title = TOPIC_DISPLAY_NAMES.get(topic, topic)
        lines.append(f"> [!abstract]- {display_title}")
        
        linked_hws = set()
        
        # Sort classwork files: foundational notes first, then chronologically by date, then alphabetically
        def cw_sort_key(item):
            fname = item[0][:-3]
            if fname in TOP_PRIORITY_NOTES:
                return (0, 0, 0, fname)
            # Look for date pattern: DD.MM (or DD-DD.MM)
            m = re.search(r"(?:(\d+)-)?(\d+)\.(\d+)(?:\.(\d+))?", fname)
            if m:
                d = int(m.group(2))
                mo = int(m.group(3))
                return (1, mo, d, fname)
            return (2, 99, 99, fname)
            
        sorted_cw = sorted(data["cw"], key=cw_sort_key)
        
        for f, full_p in sorted_cw:
            base_name = f[:-3]
            rel_cw = f"{topic}/Class work/{base_name}"
            
            # Find matching homework: explicit pair, or matching name
            matching_hw = None
            if (subject, base_name) in KNOWN_PAIRS:
                target_hw_base = KNOWN_PAIRS[(subject, base_name)]
                for hw_f, _ in data["hw"]:
                    if hw_f[:-3] == target_hw_base:
                        matching_hw = target_hw_base
                        linked_hws.add(hw_f)
                        break
            
            if not matching_hw:
                for hw_f, hw_full_p in data["hw"]:
                    hw_base = hw_f[:-3]
                    if hw_base == base_name or (base_name in hw_base) or (hw_base in base_name):
                        matching_hw = hw_base
                        linked_hws.add(hw_f)
                        break
                        
            text = load_excalidraw_text(full_p)
            desc = get_description(subject, topic, base_name, "Class work", text)
            
            lines.append(f'> - <a href="{rel_cw}" class="internal-link" target="_blank">**{base_name}**</a>')
            lines.append(f'>   > {desc}')
            if matching_hw:
                lines.append(f'>   > Home Work:  <a href="{topic}/Home work/{matching_hw}" class="internal-link" target="_blank">**{matching_hw}**</a>')
            else:
                lines.append(f'>   > Home Work:  ---')
                
        # Sort unpaired standalone homeworks: date or alphabetical
        def hw_sort_key(item):
            fname = item[0][:-3]
            m = re.search(r"(\d+)\.(\d+)(?:\.(\d+))?", fname)
            if m:
                d, mo = int(m.group(1)), int(m.group(2))
                return (mo, d, fname)
            return (99, 99, fname)
            
        unpaired_hws = [item for item in data["hw"] if item[0] not in linked_hws]
        sorted_unpaired_hws = sorted(unpaired_hws, key=hw_sort_key)
        
        for hw_f, hw_full_p in sorted_unpaired_hws:
            hw_base = hw_f[:-3]
            rel_hw = f"{topic}/Home work/{hw_base}"
            text = load_excalidraw_text(hw_full_p)
            desc = get_description(subject, topic, hw_base, "Home work", text)
            lines.append(f'> - <a href="{rel_hw}" class="internal-link" target="_blank">**{hw_base}**</a>')
            lines.append(f'>   > {desc}')
            lines.append(f'>   > Home Work:  ---')
            
        lines.append("")
        
    toc_content = "\n".join(lines).strip() + "\n"
    with open(toc_path, "w", encoding="utf-8") as fp:
        fp.write(toc_content)
        
    print(f"[{subject}] Updated {toc_name}")

if __name__ == "__main__":
    vault_root = sys.argv[1] if len(sys.argv) > 1 else "/home/petr/Documents/1/home"
    organize_vault(vault_root)
