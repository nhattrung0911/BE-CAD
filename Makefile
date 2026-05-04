.PHONY: test api worker migrate pregenerate

test:
	cd backend && PYTHONPATH=. pytest -q -p no:cacheprovider

api:
	cd backend && PYTHONPATH=. uvicorn app.main:app --reload

worker:
	cd backend && PYTHONPATH=. celery -A app.workers.tasks:celery_app worker -Q preview_fast,cad_generate,engineering_step,batch_pregenerate --loglevel=info

migrate:
	cd backend && PYTHONPATH=. alembic upgrade head

pregenerate:
	cd backend && PYTHONPATH=. python scripts/pregenerate_top_skus.py --input ../data/top_skus.example.json
