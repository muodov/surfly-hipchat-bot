check_name_env:
ifndef NAME
	$(error NAME env var is undefined)
endif

check_database_url_env:
ifndef DATABASE_URL
	$(error DATABASE_URL env var is undefined)
endif

makemigration: check_name_env check_database_url_env
	pw_migrate create --auto models --database=${DATABASE_URL} ${NAME}

makeemptymigration: check_name_env check_database_url_env
	pw_migrate create --database=${DATABASE_URL} ${NAME}

migrate: check_database_url_env
	pw_migrate migrate --database=${DATABASE_URL}

rollback: check_name_env check_database_url_env
	pw_migrate rollback --database=${DATABASE_URL} ${NAME}
