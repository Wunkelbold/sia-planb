#!/bin/bash

echo "Starting Tests"

echo "#1 Check index.html availability"
statuscode="$(curl -s -o /dev/null -w "%{http_code}" http://flask)"
echo Response: $statuscode
if test statuscode = "200"; then
    failed="$failed #1"
fi

if test -z "$failed"; then
    echo "All tests OK"
    exit 0
fi

echo "Failed at tests $failed"
exit 1