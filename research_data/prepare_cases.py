import csv, hashlib, json, pathlib, shutil
root=pathlib.Path('research_data')
cases=root/'cases'
cases.mkdir(parents=True, exist_ok=True)
# Curated text from local paper analysis, retaining page evidence in the source manifest.
(cases/'kate_method.md').write_text('''KATE (Knowledge-Augmented Tool Execution) integrates experiential knowledge across acquisition, activation, and training stages.\nThe model repeatedly predicts either a tool invocation or a final response from tools, system prompt, and dialogue history.\nThe framework compares instance-level knowledge, inference-time activation, parallel sampling, and post-training internalization.\n''', encoding='utf-8')
(cases/'atoms_method.md').write_text('''The paper proposes Atom Theory for identifying fundamental representational units in large language models.\nAtomic Inner Product (AIP) corrects representation-space geometry before comparing hidden representations.\nThreshold Sparse Autoencoder (TSAE) identifies atoms using sparse activation and a decoder whose columns represent atoms.\nExperiments evaluate representability, sparsity, separability, faithfulness R2, and stability q-star across model layers.\n''', encoding='utf-8')
with (cases/'kate_results.csv').open('w', newline='', encoding='utf-8') as f:
    w=csv.DictWriter(f, fieldnames=['benchmark','model','method','average','source'])
    w.writeheader()
    rows=[
      ('BFCL-V3','Qwen3-8B','FC',32.75,'local paper Table 1 p.7'),
      ('BFCL-V3','Qwen3-8B','KATE',46.00,'local paper Table 1 p.7'),
      ('BFCL-V3','Qwen3-8B','Direct RL',48.25,'local paper Table 1 p.7'),
      ('BFCL-V3','Qwen3-32B','FC',46.00,'local paper Table 1 p.7'),
      ('BFCL-V3','Qwen3-32B','KATE',50.50,'local paper Table 1 p.7'),
      ('AppWorld','Qwen3-8B','ReAct',4.10,'local paper Table 2 p.7'),
      ('AppWorld','Qwen3-8B','KATE',10.92,'local paper Table 2 p.7'),
      ('AppWorld','Qwen3-32B','ReAct',6.52,'local paper Table 2 p.7'),
      ('AppWorld','Qwen3-32B','Memp',9.62,'local paper Table 2 p.7'),
      ('AppWorld','Qwen3-32B','KATE',12.87,'local paper Table 2 p.7'),
    ]
    for row in rows: w.writerow(dict(zip(w.fieldnames,row)))
# Summarize public GitHub datasets without copying raw records (some fixtures contain credential-like fields).
kate_path=pathlib.Path('research_data/github/KATE/bfcl_eval/data/BFCL_v4_multi_turn_base.json')
count=0; classes={}
with kate_path.open(encoding='utf-8') as f:
    for line in f:
        if line.strip():
            item=json.loads(line); count+=1
            for c in item.get('involved_classes',[]): classes[c]=classes.get(c,0)+1
with (cases/'kate_bfcl_summary.csv').open('w', newline='', encoding='utf-8') as f:
    w=csv.DictWriter(f, fieldnames=['dataset','records','class','class_records','source'])
    w.writeheader()
    for cls,n in sorted(classes.items()): w.writerow({'dataset':'BFCL_v4_multi_turn_base','records':count,'class':cls,'class_records':n,'source':'GitHub KATE data; counts only, raw records not copied'})
# Summarize CounterFact relations from the public atoms repository.
atoms_path=pathlib.Path('research_data/github/towards_atoms/Knowledge_Atomization/data/counterfact.json')
data=json.loads(atoms_path.read_text(encoding='utf-8'))
from collections import Counter
relations=Counter(x.get('requested_rewrite',{}).get('relation_id','unknown') for x in data)
with (cases/'atoms_counterfact_summary.csv').open('w', newline='', encoding='utf-8') as f:
    w=csv.DictWriter(f, fieldnames=['dataset','records','relation_id','relation_records','source'])
    w.writeheader()
    for rel,n in relations.most_common(): w.writerow({'dataset':'CounterFact','records':len(data),'relation_id':rel,'relation_records':n,'source':'GitHub towards_atoms data; aggregate counts only'})

def sha(p):
    h=hashlib.sha256(); h.update(pathlib.Path(p).read_bytes()); return h.hexdigest()
sources={
  'kate_paper': {'title':'Pushing the Limits of LLM Tool Calling via Experiential Knowledge Integration and Activation','local_source':'E:/Desktop/论文/Pushing the Limits of LLM Tool Calling - KATE/source.pdf','arxiv':'https://arxiv.org/abs/2606.10875','github':'https://github.com/hypasd-art/KATE','license_status':'review_required','evidence':'paper-analysis.md; Tables 1-2; pages 1-2, 7, 14'},
  'atoms_paper': {'title':'Towards Atoms of Large Language Models','local_source':'E:/Desktop/论文/Towards Atoms of Large Language Models/scholar-project/source.pdf','arxiv':'https://arxiv.org/abs/2509.20784','github':'https://github.com/ChenhuiHu/towards_atoms','license_status':'review_required','evidence':'论文分析结果总结_中文版.md'},
  'kate_github': {'repository':'https://github.com/hypasd-art/KATE','local_clone':'research_data/github/KATE','dataset':'BFCL_v4_multi_turn_base.json','records':count,'license_status':'review_required'},
  'atoms_github': {'repository':'https://github.com/ChenhuiHu/towards_atoms','local_clone':'research_data/github/towards_atoms','dataset':'Knowledge_Atomization/data/counterfact.json','records':len(data),'license_status':'review_required'},
}
(root/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2), encoding='utf-8')
(root/'README.md').write_text('''# Research data\n\nThis directory contains curated, provenance-tracked inputs for the figure-agent evaluation.\n\n- `cases/kate_method.md` and `cases/atoms_method.md` are short, source-bound method excerpts from local paper analyses.\n- `cases/kate_results.csv` contains values transcribed from the local KATE paper analysis with page/table provenance.\n- `cases/kate_bfcl_summary.csv` and `cases/atoms_counterfact_summary.csv` are aggregate summaries computed from public GitHub datasets. Raw repositories remain local under `github/` and are git-ignored.\n- `sources.json` records local source paths, public URLs, and license review status.\n\nRaw benchmark records were not copied into tracked fixtures because public benchmark examples can contain credential-like fields.\n''', encoding='utf-8')
print(json.dumps({'kate_bfcl_records':count,'atoms_counterfact_records':len(data),'relations':len(relations)}, ensure_ascii=True))
