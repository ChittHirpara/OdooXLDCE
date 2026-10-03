#!/usr/bin/env bash
# Build a Champions Club database from scratch, in rupees, with the club's demo data.
#
#   scripts/create_demo_db.sh [database]        default database name: club
#
# Why not just "odoo -i club_management"? Odoo's accounting demo data creates journal entries,
# and a company's currency cannot be changed once any exist, so a normal demo install is stuck
# in dollars. This installs WITHOUT Odoo's demo data (the club switches the company to INR as it
# installs), then loads only the club's own demo files.
#
# It DROPS the database if it already exists. Run it from the repository root (Git Bash on Windows).
set -euo pipefail

DB="${1:-club}"
cd "$(dirname "$0")/.."

echo ">> database '$DB': dropping and recreating"
docker compose up -d db
for _ in $(seq 1 30); do
    docker compose exec -T db pg_isready -U odoo >/dev/null 2>&1 && break
    sleep 1
done
docker compose exec -T db dropdb -U odoo --if-exists "$DB"

echo ">> installing club_management and club_website (no Odoo demo data, company switched to INR)"
docker compose run --rm odoo odoo -d "$DB" -i club_management,club_website \
    --without-demo=all --stop-after-init --log-level=warn

echo ">> loading the club demo data"
docker compose run --rm -T odoo odoo shell -d "$DB" --no-http --log-level=warn <<'PYTHON'
env['club.demo'].install_demo_files()
env.cr.commit()
company = env.ref('base.main_company')
print("company:", company.name, "| currency:", company.currency_id.name, company.currency_id.symbol)
print("demo:", env['club.booking'].search_count([]), "bookings,",
      env['res.partner'].search_count([('is_member', '=', True)]), "members,",
      env['crm.lead'].search_count([('enquiry_ref', '!=', False)]), "enquiries")
PYTHON

echo ">> done. Start Odoo with:  docker compose up -d   then open http://localhost:8069  (admin / admin, database '$DB')"
