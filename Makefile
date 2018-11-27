PATH := node_modules/.bin:$(PATH)

deploy-apex: project.json deps/deps.tgz
	apex deploy -l debug -E environment.json

.PHONY: project.json
project.json: project.json.hbs node_modules/.bin/interp
	interp < $< > $@

deploy-up: up.json deps/deps.tgz
	up $(ENV)

# always build this in case the *environment* changes
.PHONY: up.json
up.json: up.json.hbs node_modules/.bin/interp
	interp < $< > $@

node_modules/.bin/interp:
	npm install interp

deps/deps.tgz: deps/Dockerfile deps/required.txt
	docker run --rm --entrypoint tar $$(docker build --build-arg http_proxy=$(http_proxy) -t marblecutter-virtual-deps -q -f $< .) zc -C /var/task . > $@

clean:
	rm -f deps/deps.tgz

server:
	docker build --build-arg http_proxy=$(http_proxy) -t quay.io/mojodna/marblecutter-virtual .

run:
	docker run -p 8000:8000 \
	 -v `pwd`:/opt/marblecutter \
	 --entrypoint="/bin/bash" -i -t \
	 --user=root \
	 --rm \
	 marblecuttervirtual_marblecutter:latest
	#gunicorn -k gevent -b 0.0.0.0 --access-logfile - virtual.web:app
	#cd marblecutter/ && pip install -e . && cd .. && gunicorn -k gevent -b 0.0.0.0 --access-logfile - virtual.web:app