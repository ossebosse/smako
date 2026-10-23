import ast
import hashlib
import json
import subprocess
from pathlib import Path


def source(commit,path):
    return subprocess.check_output(['git','show',f'{commit}:{path}'],text=True,encoding='utf8')

def digest(tree):
    return hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest()

old='c9390dd';new='b139cd4'
menu_path='backend/app/services/menu_optimizer.py';planner_path='backend/app/services/personal_planner.py'
old_menu=ast.parse(source(old,menu_path));new_menu=ast.parse(source(new,menu_path))
cls=next(n for n in new_menu.body if isinstance(n,ast.ClassDef) and n.name=='MenuOptimizer')
added=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='dish_form_capacity_conflict'];assert len(added)==1
cls.body.remove(added[0]);assert ast.dump(old_menu)==ast.dump(new_menu)
old_planner=ast.parse(source(old,planner_path));new_planner=ast.parse(source(new,planner_path))
old_create=next(n for n in ast.walk(old_planner) if isinstance(n,ast.FunctionDef) and n.name=='_create')
assert not any(isinstance(n,ast.Name) and n.id=='capacity' for n in ast.walk(old_create))
removed=0
for node in ast.walk(new_planner):
    if isinstance(node,ast.With) and len(node.body)>=2:
        first,second=node.body[:2]
        if (isinstance(first,ast.Assign) and len(first.targets)==1 and isinstance(first.targets[0],ast.Name)
                and first.targets[0].id=='capacity' and isinstance(second,ast.If)
                and isinstance(second.test,ast.Compare) and isinstance(second.test.left,ast.Name)
                and second.test.left.id=='capacity'):
            del node.body[:2];removed+=1
assert removed==1 and ast.dump(old_planner)==ast.dump(new_planner)
changed=subprocess.check_output(['git','diff','--name-only',old,new,'--','backend/app'],text=True).splitlines()
assert set(changed)=={menu_path,planner_path}
proof={'schema':'capacity-only-change-proof-v1','from_commit':old,'to_commit':new,'changed_app_files':changed,
       'all_preexisting_menu_optimizer_code_ast_unchanged':True,'menu_optimizer_ast_sha256':digest(old_menu),
       'all_preexisting_personal_planner_code_ast_unchanged':True,'personal_planner_ast_sha256':digest(old_planner),
       'new_local_does_not_shadow_existing_create_binding':True,
       'new_behavior':'Necessary capacity bound only. A previously accepted complete menu proves the rejection condition false.',
       'reuse_scope':'Successful fixed-input matrix searches on c9390dd; blocked cases measured on b139cd4. Timing versions remain explicit.'}
Path('docs/reviews/integration-scaling-20261023/capacity-code-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8')
print(json.dumps(proof))
