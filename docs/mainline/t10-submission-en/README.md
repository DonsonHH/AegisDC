# Expert Systems with Applications submission candidate

**When is a paid inspection worth waiting for during maintenance-induced degradation?**

[Editable review manuscript](manuscript.docx) · [Review PDF](manuscript.pdf) · [English source with numbered references](manuscript.md) · [Verification](verification.md) · [File digests](SHA256SUMS.txt)

The Chinese candidate at [361574a0](https://github.com/DonsonHH/AegisDC/tree/361574a049f0cfbf816f62af92ff5fd398d77ae8/docs/mainline/t9-submission-r1) supplied the entire scientific content. The [English claims](claims-en.md) were published separately at [fec03bd3](https://github.com/DonsonHH/AegisDC/commit/fec03bd390b1bd294afc98975a1afbc9ab7b3566) before drafting. The article is prepared for *Expert Systems with Applications*. The PI controls formal submission.

## Which file goes where

| Purpose | File | Use |
|---|---|---|
| Main article | [Word](manuscript.docx) and [PDF](manuscript.pdf) | Single-column review copy. Five native editable tables, captions, three embedded English vectors, author–date references, data availability and AI disclosure. The article omits the author list and private or owner-identifying URLs. |
| Author information | [Separate title page](submission/title-page.docx) | PI completes the byline, order, affiliations, address, contact details, funding and acknowledgements. |
| Editor's letter | [Cover letter](submission/cover-letter.docx) | Addresses the decision-support contribution, retained counterexamples, FIT closeout and absence of an established RSI increment. PI supplies the signature. |
| Highlights | [Highlights](submission/highlights.docx) | Separate editable bullets. |
| Availability | [Data and code statement](submission/data-and-code-availability.docx) | Includes the article statement and a separate public repository and revision for the editor or post-review publication. |
| Contribution roles | [CRediT statement](submission/credit-statement.docx) | Named authors assign and approve their actual roles. |
| Interests | [Competing interests](submission/competing-interests.docx) | Contains an author-completion field and conditional no-interest wording. Each author must confirm the applicable declaration. |
| AI assistance | [AI disclosure](submission/ai-declaration.docx) | Identifies drafting, translation, programming and figure-label typesetting. Human authors review the English publication and decide whether to submit it. |
| Reporting | [STRESS checklist](submission/stress-checklist.docx) | Maps each reporting item to the article and identifies partial coverage, including historical machine specifications. |
| Figure uploads | [Facility boundary](figures/facility-information-boundary.pdf), [incident directions](figures/T7-paired-directions.pdf), [edit effects](figures/T8-edit-tradeoffs.pdf) | Single-page vector PDFs. Editable SVGs with matching names are in the same directory. The marks, scales and scientific labels are checked against the Chinese originals. |

The text companions in `submission/` are editable sources for the Word attachments. The numbered manuscript is the bilingual verification copy. The review copy presents the same twelve works in author–date style. The two Google Cloud reports are dated separately. Their suffixes map to the accepted numbered sources in the [reference crosswalk](reference-crosswalk.tsv). The extended author lists for the existing Frontier and ExaDigiT records follow their publisher-deposited DOI metadata. The sources and scientific claims did not change.

## What the PI still decides

Supply the title-page details and agreed CRediT roles. Confirm interests and funding with all authors, check the AI disclosure against the tools used, review the English text and sign the editor's letter. The public study and its revision identifiers remain discoverable. Keep this repository-facing index and the numeric ledger on the PI side during anonymous review. If the editor requests reviewer access to supporting material, the PI selects the sharing channel. The PI completes the live portal declarations and sends the submission.

The package follows the user-specified abstract, keyword and highlight limits. Publisher scope, the journal’s author-information pack and Elsevier’s AI policy informed the preparation. The publisher’s live ScienceDirect instructions were unavailable to the verification clients. The PI should confirm any current portal-specific fields at filing. [Journal scope](https://shop.elsevier.com/journals/expert-systems-with-applications/0957-4174) · [ESWA author-information pack](https://citeseerx.ist.psu.edu/document?doi=1397dbf0787cc72cd7145f4a386d6248ae75a05b&repid=rep1&type=pdf) · [Current guide](https://www.sciencedirect.com/journal/expert-systems-with-applications/publish/guide-for-authors) · [Publisher AI policy](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals)

## Verification and reproduction

The [per-occurrence inventory](numeric-ledger.tsv) identifies the accepted source commit, file, line, table cell or figure element and the corresponding English expression. It covers scientific values and their repeated appearances, along with identifiers, signed intervals, written counts, citations and numeric links. Chart data marks are compared separately from the translated type. A public checker reads the actual editable document and its printed PDF and locates the rendered figures on the page.

From this directory in a fresh Git checkout with the pinned public revisions available, run:

```text
python -X utf8 -B verify.py --check --checkout-bytes
```

The check uses Python, Git, pypdf, lxml, Beautiful Soup, markdown-it-py, OpenCV, and the Poppler tools `pdfinfo` and `pdftoppm`. Publication building on Windows additionally needs python-docx, pywin32, Microsoft Word, Playwright and Chrome/Chromium. The recorded file digests identify the released outputs. Native PDF/Word producers can change timestamps on re-export. To build the publication files from the accepted material in a separate copy and write a new digest index, use:

```text
python -X utf8 -B build.py --browser-executable "<Chrome or Chromium executable>"
python -X utf8 -B verify.py --write-records
```

[SHA256SUMS.txt](SHA256SUMS.txt) covers every delivered file except the index itself. Its own SHA-256 is reported in the delivery message. Formatting and verification operate on published documents and vectors, without a facility call, scoring run, Slurm job or access to sealed H2/H3 material. The three untracked historical scripts were privately archived with verified backups before the claim lock. The private receipt stays outside Git.
