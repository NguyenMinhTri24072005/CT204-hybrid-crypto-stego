# latexmk: biên dịch bằng XeLaTeX (dùng được với LaTeX Workshop trong VS Code)
$pdf_mode = 5;
$xelatex = 'xelatex -synctex=1 -interaction=nonstopmode -file-line-error %O %S';
$bibtex_use = 2;
$out_dir = '.';
$clean_ext = 'bbl synctex.gz xdv run.xml lol';
