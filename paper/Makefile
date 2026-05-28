PDFLATEX ?= pdflatex
BIBTEX ?= bibtex
PAPER_BASENAME := When_Memory_Metrics_Hide_Memory_Policies
PAPER_PDF := $(PAPER_BASENAME).pdf

ARXIV_STAGE := arxiv-stage
ARXIV_TARBALL := arxiv-source.tar.gz

.PHONY: all clean verify-artifacts arxiv-archive arxiv-clean

all: $(PAPER_PDF)

$(PAPER_PDF): main.tex abstract.tex bibliography.bib sections/*.tex appendices/*.tex figures/*.png figures/*.tex
	$(PDFLATEX) -interaction=nonstopmode -jobname=$(PAPER_BASENAME) main.tex
	-$(BIBTEX) $(PAPER_BASENAME)
	$(PDFLATEX) -interaction=nonstopmode -jobname=$(PAPER_BASENAME) main.tex
	$(PDFLATEX) -interaction=nonstopmode -jobname=$(PAPER_BASENAME) main.tex

verify-artifacts:
	sh repro/verify_artifact_paths.sh

# Build a clean arXiv submission tarball.
# Includes only compile-needed source + figures + a renamed main.bbl.
# Excludes Makefile, aux/log/out/blg, the generated PDF, the repro/ tree,
# and the PNG mirrors of the quantitative figures (PDFLaTeX prefers PDF).
arxiv-archive: $(PAPER_PDF)
	@if [ ! -f $(PAPER_BASENAME).bbl ]; then \
	  echo "ERROR: $(PAPER_BASENAME).bbl not found. Run 'make' first."; \
	  exit 1; \
	fi
	@rm -rf $(ARXIV_STAGE) $(ARXIV_TARBALL)
	@mkdir -p $(ARXIV_STAGE)/sections $(ARXIV_STAGE)/appendices $(ARXIV_STAGE)/figures
	@cp main.tex abstract.tex bibliography.bib $(ARXIV_STAGE)/
	@cp sections/*.tex $(ARXIV_STAGE)/sections/
	@cp appendices/*.tex $(ARXIV_STAGE)/appendices/
	@cp figures/*.tex $(ARXIV_STAGE)/figures/
	@cp figures/*.pdf $(ARXIV_STAGE)/figures/
	@cp $(PAPER_BASENAME).bbl $(ARXIV_STAGE)/main.bbl
	@tar -czf $(ARXIV_TARBALL) -C $(ARXIV_STAGE) .
	@rm -rf $(ARXIV_STAGE)
	@echo ""
	@echo "arXiv source archive ready: paper/$(ARXIV_TARBALL)"
	@echo "Contents:"
	@tar -tzf $(ARXIV_TARBALL) | sort | sed 's/^/  /'
	@echo ""
	@echo "Sanity check before upload:"
	@echo "  - root .tex is main.tex (arXiv default)"
	@echo "  - prebuilt bibliography is main.bbl (matches root)"
	@echo "  - no aux/log/out/blg/PDF in archive"
	@echo "  - figures include only .tex (TikZ) and .pdf (raster) — no .png"

arxiv-clean:
	rm -rf $(ARXIV_STAGE) $(ARXIV_TARBALL)

clean: arxiv-clean
	rm -f main.aux main.bbl main.blg main.log main.out main.toc
	rm -f $(PAPER_BASENAME).aux $(PAPER_BASENAME).bbl $(PAPER_BASENAME).blg
	rm -f $(PAPER_BASENAME).log $(PAPER_BASENAME).out $(PAPER_PDF) $(PAPER_BASENAME).toc
