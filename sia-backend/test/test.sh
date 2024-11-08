#!/bin/bash

echo "Starting Tests"

# ----- Test #1 -----

echo "#1 Check index.html availability"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask)"
echo Response: $statuscode
if test $statuscode != "200"; then
    failed="$failed #1"
fi

# ----- Test #2 -----

echo "#2 Check if non-existent path not exists"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask/this-path-does-not-exist)"
echo Response: $statuscode
if test $statuscode != "404"; then
    failed="$failed #2"
fi

# ----- Tests Done -----

if test -z "$failed"; then
    echo "All tests OK"
    exit 
fi

echo "Failed at tests$failed"
exit 1
