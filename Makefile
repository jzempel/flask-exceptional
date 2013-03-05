.PHONY: clean upload

clean:
	rm -rf Flask_Exceptional.egg-info
	rm -rf dist
	rm -rf docs/_build
	rm -rf docs/_themes
	git checkout docs/_themes

upload: docs/_build
	python setup.py sdist upload
	python setup.py upload_sphinx

docs/_build: docs/_themes/README
	python setup.py develop
	python setup.py build_sphinx

docs/_themes/README:
	git submodule init
	git submodule update
	git submodule foreach git pull origin master
