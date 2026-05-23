PDFLATEX ?= pdflatex
BIBTEX ?= bibtex
PAPER_BASENAME := When_Memory_Metrics_Hide_Memory_Policies
PAPER_PDF := $(PAPER_BASENAME).pdf

.PHONY: all clean verify-artifacts

all: $(PAPER_PDF)

$(PAPER_PDF): main.tex abstract.tex bibliography.bib sections/*.tex appendices/*.tex figures/*.png figures/*.tex
	$(PDFLATEX) -interaction=nonstopmode -jobname=$(PAPER_BASENAME) main.tex
	-$(BIBTEX) $(PAPER_BASENAME)
	$(PDFLATEX) -interaction=nonstopmode -jobname=$(PAPER_BASENAME) main.tex
	$(PDFLATEX) -interaction=nonstopmode -jobname=$(PAPER_BASENAME) main.tex

verify-artifacts:
	sh repro/verify_artifact_paths.sh

clean:
	rm -f main.aux main.bbl main.blg main.log main.out main.toc
	rm -f $(PAPER_BASENAME).aux $(PAPER_BASENAME).bbl $(PAPER_BASENAME).blg
	rm -f $(PAPER_BASENAME).log $(PAPER_BASENAME).out $(PAPER_PDF) $(PAPER_BASENAME).toc
