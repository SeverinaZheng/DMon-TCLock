python3 apply_coccinelle.py 2>/dev/null
python3 adapt_to_bpf.py
cd ~
diff -ruN SynCord-linux-base  SynCord-linux-destination > template.patch
