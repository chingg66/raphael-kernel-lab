import yaml, sys
p = r'C:\Users\Chen\Documents\deepseek-harness\default-workspace\kernel-lab\raphael-ci\.github\workflows\build-raphael.yml'
d = yaml.safe_load(open(p, encoding='utf-8'))
steps = d['jobs']['build']['steps']
print('YAML OK; steps:', len(steps))
for s in steps:
    r = s.get('run')
    if r:
        print(f"  {len(r):6d}  {s.get('name','?')[:60]}")
