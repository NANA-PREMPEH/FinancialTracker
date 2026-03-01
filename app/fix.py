import re

with open('models.py', 'r', encoding='utf-8') as f:
    content = f.read()

classes = re.split(r'^(?=class )', content, flags=re.MULTILINE)
new_content = ""

for cls_text in classes:
    if not cls_text.startswith('class '):
        new_content += cls_text
        continue

    cls_name_match = re.match(r'class (\w+)\(', cls_text)
    if not cls_name_match:
        new_content += cls_text
        continue
        
    cls_name = cls_name_match.group(1)
    
    if "db.ForeignKey('user.id')" in cls_text:
        rel_match = re.search(r"(user\s*=\s*db\.relationship\([^)]+backref\s*=\s*)(['\"a-zA-Z_]+)(\s*,[^)]*\))", cls_text)
        
        if rel_match:
            backref_val = rel_match.group(2)
            if 'db.backref' not in backref_val and 'cascade' not in cls_text:
                new_rel = f"{rel_match.group(1)}db.backref({backref_val}, cascade='all, delete-orphan'){rel_match.group(3)}"
                cls_text = cls_text[:rel_match.start()] + new_rel + cls_text[rel_match.end():]
        else:
            plural = cls_name.lower() + 's'
            if plural.endswith('ys'): plural = plural[:-2] + 'ies'
            
            rel_str = f"    user = db.relationship('User', backref=db.backref('_user_{plural}', cascade='all, delete-orphan'), lazy=True)"
            
            repr_match = re.search(r'^    def __repr__\(self\):', cls_text, flags=re.MULTILINE)
            if repr_match:
                cls_text = cls_text[:repr_match.start()] + rel_str + "\n\n" + cls_text[repr_match.start():]
            else:
                cls_text += "\n" + rel_str + "\n"

    new_content += cls_text

with open('models.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("models.py updated successfully!")
