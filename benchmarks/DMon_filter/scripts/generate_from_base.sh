LOCK_TYPE="$1"
LOCK_STRUCTURE="$2"
NEW_LOCK="$3"
python3 apply_coccinelle.py $LOCK_TYPE $LOCK_STRUCTURE $NEW_LOCK 2>/dev/null
python3 adapt_to_bpf.py $LOCK_TYPE
cd ~
diff -ruN SynCord-linux-base  SynCord-linux-destination > template.patch
