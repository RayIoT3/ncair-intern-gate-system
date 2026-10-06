"""Baseline intern records, generated the same way on every machine (fixed random seed)."""
import random

# These are the five active project members. Their IDs remain placeholders until
# the team confirms the real IDs; keep existing IDs stable for saved records/tests.
TEAM = [
    ("Raymond Udoh", "NC-SI-000001"),
    ("Chigozie Nwofor", "NC-SI-000002"),
    ("Isaac Erameh", "NC-SI-000003"),
    ("Jessie Nyiyongo", "NC-SI-000005"),
    ("Abdurrahman Ibrahim", "NC-SI-000006"),
]

FIRST = ["Amina", "Chinedu", "Tunde", "Zainab", "Emeka", "Hauwa", "Ibrahim", "Ngozi", "Samuel", "Fatima",
         "David", "Blessing", "Musa", "Grace", "Peter", "Halima", "Kelechi", "Aisha", "John", "Rukayya",
         "Ifeanyi", "Chiamaka", "Yusuf", "Folake", "Obinna", "Nneka", "Abubakar", "Sadiq", "Temitope", "Oluwaseun",
         "Bukola", "Uche", "Maryam", "Sani", "Lawal", "Esther", "Daniel", "Precious", "Ahmed", "Joy"]
LAST = ["Yusuf", "Okafor", "Bakare", "Musa", "Eze", "Bello", "Sani", "Obi", "Adeyemi", "Lawal",
        "Ojo", "Udo", "Garba", "Nwosu", "Danjuma", "Abubakar", "Ibe", "Umar", "Effiong", "Aliyu",
        "Balogun", "Okonkwo", "Adebayo", "Ali", "Chukwu", "Okoro", "Suleiman", "Akpan", "Onyeka", "Idris",
        "Salisu", "Abdullahi", "Ogunleye", "Afolabi", "Mohammed", "Uzor", "Etim", "Ekpo", "Nnamdi", "Hassan"]
DEPARTMENTS = ["Software Development", "Robotics", "Artificial Intelligence", "Data & Analytics",
               "Cybersecurity", "Networks & Infrastructure", "E-Government Services", "Research & Innovation"]


def generate_interns(count=320, seed=23):
    """Return `count` intern dicts (team members first), all OUTSIDE, with unique IDs and names."""
    rng = random.Random(seed)
    records, names = [], set()

    def add(name, iid):
        names.add(name)
        records.append({"intern_id": iid, "name": name, "department": rng.choice(DEPARTMENTS),
                        "phone": f"080{rng.randrange(10 ** 8):08d}",
                        "email": name.lower().replace(" ", ".") + "@example.com", "status": "OUTSIDE"})

    for name, iid in TEAM[:count]:
        add(name, iid)
    counters = {"NY": 101, "SI": 101}
    while len(records) < count:
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if name in names:
            continue
        kind = rng.choice(("NY", "SI"))
        add(name, f"NC-{kind}-{counters[kind]:06d}")
        counters[kind] += 1
    return records
