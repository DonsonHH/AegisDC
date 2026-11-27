# T11-3 publication handoff

Start with the review PDF and editable manuscript. Read the figures and the development comparisons together with their denominators. The abstract reports the preregistered results and the full-panel supplementary interpretation. The paper's final section and the claim lock retain the failed transfer and the unestablished rewrite increment.

## Rechecking this release

- Use `python -X utf8 -B docs/mainline/t11-eswa-revision/t11-3/verify.py --check --checkout-bytes` on a fresh checkout of the published commit. The verifier reads released Git blobs, checks the Word and printed text, and measures the actual PDF geometry. It imports no scientific engine or analysis script.
- T11-1's original checkout verifier intentionally rejects any change outside its own package since its original base. For the appended accounting record, run that verifier at its **accounting commit** `10b3f7a08462623c22b87b3ae0dae7abe3c95378`. The new checker compares those exact accounting blobs at the current tip. The gaps in job IDs belong to other cluster accounts.
- The parent Git attributes force LF conversion throughout the revision directory. The scoped attributes preserve PDF, DOCX, ZIP and the exact SVG bytes embedded in Word. Matplotlib emitted CRLF on this workstation. Compare the index blob with the embedded artwork before committing.
- The earlier Word helper hard-codes one maintenance table width. This edition sizes each native table by its own column count. Short tables stay with their headers, and the timing legend has its own space. Recheck the actual exported PDF after reflow.
- To rebuild the editorial files in a disposable checkout on Windows with the existing authoring dependencies, run `python -X utf8 -B docs/mainline/t11-eswa-revision/t11-3/publication.py`. It uses python-docx, Microsoft Word, the installed Office MathML transform, Matplotlib and the accepted T10 typography helpers. The checker additionally needs pypdf, lxml, Beautiful Soup, markdown-it-py, NumPy, OpenCV and the Poppler pdfinfo and pdftoppm commands. Binary office timestamps may change on a new export. Scientific source versions and input identities are listed in Supplement A.

Study execution, sealed materials and journal submission all remain outside this editorial handoff.
