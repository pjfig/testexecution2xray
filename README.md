# Main files

** auth.conf ** OAuth configuration file

** constants.py ** Constants used in the whole project

** jira_privatekey.pem ** Private key used for OAuth

** rfw2xray_auth.py ** Creates an oauth client

** rfw2xray_results.py ** Main module, that imports robot framework output to xray.

** rfw2xray_results.1.py ** Main module, that imports robot framework output to xray, v.2 (through OAuth and Test Execution JSON translator)

** testexec_builder.py ** Module that performs translation of 'rfw2xray_results.1.py' 's elements to JSON

** testexec_translator.json ** JSON File with translation specification




# Extra

** add-tags-xml.py ** Script to add incrementally tags to Robot Framework's output xml. Requires xml file, tag to add, project key, minimum and higher tag value.

Generates a new xml file named "sample_output".xml with selected tag in its test cases. **In development** Example:

```
add-tags.py PATH/TO/ROBOTFRAMEWORKOUTPUT.xml/ JIRA_TAG PROJECTKEY 10 21
```

** create-jira-test.py ** Script to create JIRA Test Issue using the Robot Framework output file. Requires Robot Framework's output file as input.
```
create-jira-test.py PATH/TO/ROBOTFRAMEWORKOUTPUT.xml/
```


