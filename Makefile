THIS_FILE := $(lastword $(MAKEFILE_LIST))
include .env

.PHONY: ls start-network nstart start-db dstart stop-db dstop clean-db-container dcclean build-tagger tbuild start-tagger tstart stop-tagger tstop clean-tagger-container tcclean
ls:
	@$(MAKE) -pRrq -f $(THIS_FILE) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'

# Network
start-network:
	docker network create "${TMV_NETWORK_NAME}"
nstart: start-network

# Database
start-db:
	docker pull "postgres:${TMV_DB_IMAGE_VERSION}"
	docker run "--name=${TMV_DB_CONTAINER_NAME}" "--network=${TMV_NETWORK_NAME}" "--network-alias=${TMV_DB_NETWORK_ALIAS}" "-p${TMV_DB_PORT}:5432" -v "${TMV_DB_VOLUME_LOCATION}:/var/lib/postgresql/data" -e "POSTGRES_DB=${TMV_DB_NAME}" -e "POSTGRES_USER=${TMV_DB_USER}" -e "POSTGRES_PASSWORD=${TMV_DB_PASSWORD}" -d "postgres:${TMV_DB_IMAGE_VERSION}"
dstart: start-db

stop-db:
	docker stop "${TMV_DB_CONTAINER_NAME}"
dstop: stop-db

clean-db-container: stop-db
	docker container rm "${TMV_DB_CONTAINER_NAME}"
dcclean: clean-db-container

# Tagger
build-tagger:
	docker build -t tmv-tagger:latest -f Tagger-Dockerfile .
tbuild: build-tagger

start-tagger:
	docker run "--name=${TMV_TAGGER_CONTAINER_NAME}" "--network=${TMV_NETWORK_NAME}" "--network-alias=${TMV_TAGGER_NETWORK_ALIAS}" "-p${TMV_TAGGER_PORT}:8000" -d "${TMV_TAGGER_IMAGE_NAME}:${TMV_TAGGER_IMAGE_VERSION}"
tstart: start-tagger

stop-tagger:
	docker stop "${TMV_TAGGER_CONTAINER_NAME}"
tstop: stop-tagger

clean-tagger-container: stop-tagger
	docker container rm "${TMV_TAGGER_CONTAINER_NAME}"
tcclean: clean-tagger-container
