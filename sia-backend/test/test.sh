#!/bin/sh

failed=""

echo "Starting Tests"

# ----- Test #1 -----

echo "#1 Check index.html availability"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask)"
echo "Response: $statuscode"
if test "$statuscode" != "200"; then
    failed="$failed #1"
fi

# ----- Test #2 -----

echo "#2 Check if non-existent path not exists"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/this-path-does-not-exist)"
echo "Response: $statuscode"
if test "$statuscode" != "404"; then
    failed="$failed #2"
fi

# ----- Test #3 -----

echo "#3 Check frontend API health endpoint"
health="$(curl -fsS http://flask/api/v1/health 2>/dev/null)"
if test "$health" != '{"status":"ok"}'; then
    echo "Unexpected API health response"
    failed="$failed #3"
fi

# ----- Test #4 -----

echo "#4 Check public upcoming-events API"
events="$(curl -fsS http://flask/api/v1/events 2>/dev/null)"
case "$events" in
    *'"events":['*) ;;
    *)
        echo "Unexpected events API response"
        failed="$failed #4"
        ;;
esac

# ----- Test #5 -----

echo "#5 Check anonymous frontend session state"
session="$(curl -fsS http://flask/api/v1/session 2>/dev/null)"
case "$session" in
    *'"authenticated":false'*) ;;
    *)
        echo "Unexpected anonymous session response"
        failed="$failed #5"
        ;;
esac

# ----- Test #6 -----

echo "#6 Check missing event details return 404"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/events/2147483647)"
echo "Response: $statuscode"
if test "$statuscode" != "404"; then
    failed="$failed #6"
fi

# ----- Test #7 -----

echo "#7 Keep personal tickets behind authentication"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/me/tickets)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #7"
fi

# ----- Test #8 -----

echo "#8 Keep profile data behind authentication"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/me/profile)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #8"
fi

# ----- Test #9 -----

echo "#9 Keep the CAPTCHA solution out of the registration setup payload"
registration_setup="$(curl -fsS http://flask/api/v1/auth/register 2>/dev/null)"
if ! printf '%s' "$registration_setup" | grep -q '"captcha"' || printf '%s' "$registration_setup" | grep -q '"text"[[:space:]]*:'; then
    echo "Unexpected registration CAPTCHA payload"
    failed="$failed #9"
fi

# ----- Test #10 -----

echo "#10 Keep event management behind organizer permissions"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/manage/events)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #10"
fi

# ----- Test #11 -----

echo "#11 Keep organizer task management behind permissions"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/manage/events/2147483647/tasks)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #11"
fi

# ----- Test #12 -----

echo "#12 Check anonymous contact-form setup does not expose CAPTCHA answers"
contact_setup="$(curl -fsS http://flask/api/v1/contact 2>/dev/null)"
if ! printf '%s' "$contact_setup" | grep -q '"captcha"' || printf '%s' "$contact_setup" | grep -q '"text"[[:space:]]*:'; then
    echo "Unexpected contact-form setup response"
    failed="$failed #12"
fi

# ----- Test #13 -----

echo "#13 Keep admin user management behind permissions"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/manage/users)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #13"
fi

# ----- Test #14 -----

echo "#14 Keep admin contact requests behind permissions"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/manage/contacts)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #14"
fi

# ----- Test #15 -----

echo "#15 Keep personal commitments behind authentication"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/me/commitments)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #15"
fi

# ----- Test #16 -----

echo "#16 Require CSRF validation for email verification requests"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" -X POST http://flask/api/v1/me/verification)"
echo "Response: $statuscode"
if test "$statuscode" != "400"; then
    failed="$failed #16"
fi

# ----- Test #17 -----

echo "#17 Keep the cross-event task overview behind permissions"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/manage/tasks)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #17"
fi

# ----- Test #18 -----

echo "#18 Require CSRF validation for password reset requests"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" -X POST http://flask/api/v1/auth/password-reset)"
echo "Response: $statuscode"
if test "$statuscode" != "400"; then
    failed="$failed #18"
fi

# ----- Test #19 -----

echo "#19 Require CSRF validation for password reset confirmation"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" -X POST http://flask/api/v1/auth/password-reset/confirm)"
echo "Response: $statuscode"
if test "$statuscode" != "400"; then
    failed="$failed #19"
fi

# ----- Test #20 -----

echo "#20 Keep member finances behind authentication"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/me/finances)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #20"
fi

# ----- Test #21 -----

echo "#21 Keep admin finance data behind permissions"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/manage/finance)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #21"
fi

# ----- Test #22 -----

echo "#22 Require CSRF validation for tally purchases"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" -X POST http://flask/api/v1/me/finance/purchases)"
echo "Response: $statuscode"
if test "$statuscode" != "400"; then
    failed="$failed #22"
fi

# ----- Test #23 -----

echo "#23 Keep annual billing previews behind finance permissions"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/api/v1/manage/finance/billing-preview/2027)"
echo "Response: $statuscode"
if test "$statuscode" != "401"; then
    failed="$failed #23"
fi

# ----- Test #24 -----

echo "#24 Require CSRF validation for finance reminder emails"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" -X POST http://flask/api/v1/manage/finance/reminders)"
echo "Response: $statuscode"
if test "$statuscode" != "400"; then
    failed="$failed #24"
fi

# ----- Test #25 -----

echo "#25 Require CSRF validation for annual student verification requests"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" -X POST http://flask/api/v1/me/student-verification)"
echo "Response: $statuscode"
if test "$statuscode" != "400"; then
    failed="$failed #25"
fi

# ----- Test #26 -----

echo "#26 Require CSRF validation for bulk student re-verification"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" -X POST http://flask/api/v1/manage/finance/student-verifications)"
echo "Response: $statuscode"
if test "$statuscode" != "400"; then
    failed="$failed #26"
fi

# ----- Test #27 -----

echo "#27 Require CSRF validation for bulk tally confirmation"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" -X POST http://flask/api/v1/manage/finance/memberships/00000000-0000-0000-0000-000000000000/confirm-open-tally)"
echo "Response: $statuscode"
if test "$statuscode" != "400"; then
    failed="$failed #27"
fi

# ----- Test #28 -----

echo "#28 Require CSRF validation for billing-run void requests"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" -X POST http://flask/api/v1/manage/finance/billing-runs/1/void)"
echo "Response: $statuscode"
if test "$statuscode" != "400"; then
    failed="$failed #28"
fi

# ----- Tests Done -----

if test -z "$failed"; then
    echo "All tests OK"
    exit 0
fi

echo "Failed at tests$failed"
exit 1
