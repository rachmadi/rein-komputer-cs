import sys
sys.path.append('.')
import json
from services.llm_parser import parse_user_message

with open('eval/parse_gold.jsonl', 'r', encoding='utf-8') as f:
    items = {item['id']: item for item in (json.loads(line) for line in f if line.strip())}

test_ids = ['dev-005', 'dev-004', 'dev-010', 'dev-023', 'dev-027', 'dev-028', 'dev-034', 'dev-039']
print('Evaluating dev-005 and 7 dev errors on clean prompt:')
results = []
for tid in test_ids:
    item = items[tid]
    pred, metrics = parse_user_message(item['pesan'], state=item.get('state', {}))
    is_correct = (pred.aksi.value == item['label_aksi'])
    print(f'[{tid}] "{item["pesan"]}"')
    print(f'  Gold: {item["label_aksi"]} | Pred: {pred.aksi.value} | Correct: {is_correct}')
    print(f'  Pred Args: {pred.argumen.model_dump(exclude_unset=True)}')
    results.append({
        'id': tid,
        'pesan': item['pesan'],
        'gold_aksi': item['label_aksi'],
        'gold_argumen': item['label_argumen'],
        'pred': pred.model_dump(),
        'correct': is_correct,
        'metrics': metrics
    })

with open('eval/dev_errors_clean_result.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
