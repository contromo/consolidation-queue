PDFLATEX ?= pdflatex
BIBTEX ?= bibtex

.PHONY: all clean verify-artifacts

all: main.pdf

main.pdf: main.tex abstract.tex bibliography.bib sections/*.tex appendices/*.tex figures/*.png
	$(PDFLATEX) -interaction=nonstopmode main.tex
	-$(BIBTEX) main
	$(PDFLATEX) -interaction=nonstopmode main.tex
	$(PDFLATEX) -interaction=nonstopmode main.tex

verify-artifacts:
	sh repro/verify_artifact_paths.sh

clean:
	rm -f main.aux main.bbl main.blg main.log main.out main.pdf main.toc
