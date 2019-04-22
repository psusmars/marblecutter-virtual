PATH := node_modules/.bin:$(PATH)
STACK_NAME ?= "marblecutter-virtual"

deploy: packaged.yaml
	sam deploy \
		--template-file $< \
		--stack-name $(STACK_NAME) \
		--capabilities CAPABILITY_IAM \
		--parameter-overrides DomainName=$(DOMAIN_NAME) \
		--parameter-overrides AcmCertificateArn=$(ACM_ARN)

packaged.yaml: .aws-sam/build/template.yaml
	sam package --s3-bucket $(S3_BUCKET) --output-template-file $@

.aws-sam/build/template.yaml: template.yaml requirements.txt virtual/*.py
	sam build --use-container

clean:
	rm -rf .aws-sam/ packaged.yaml

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