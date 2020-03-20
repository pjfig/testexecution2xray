import json
import constants as c
import os
translator = {
    "testexec_key" : "testExecutionKey",
    "project" : "info/project",
    "summary" : "info/summary",
    "description" :"info/description",
    "user" : "info/user",
    "version" : "info/version",
    "revision" : "info/revision",
    "startDate" : "info/startDate",
    "finishDate" : "info/finishDate",
    "testPlanKey" : "info/testPlayKey",
    "tests" : "tests",

    "test_comment" : "comment",
    "test_status" : "status",
    "test_finish" : "finish",
    "test_start" : "start",
    "test_testKey" : "testKey",
    "test_executedBy": "executedBy",
    "test_evidences" : "evidences",

    "evidence_data" : "data",
    "evidence_filename" : "filename",
    "evidence_contentType" : "contentType",

    "steps" : "steps",
    
    "step_status" : "status",
    "step_comment" : "comment",
    "step_evidences" : "evidences"  
}


#    translator = json.load(f)


# Get a path from the JSON dict
def path_get(dictionary, path):
    path = translator[path]
    try:
        for item in path.split("/"):
            dictionary = dictionary[item]
    except:
        return None
    return dictionary


# Set a value in the JSON dict path
def path_set(dictionary, path, setItem):
    path = translator[path]
    path = path.split("/")
    key = path[-1]
    if len(path) > 1:
        dictionary = path_get(dictionary, "/".join(path[:-1]))
    dictionary[key] = setItem

# New entry to dict
def path_new(dictionary, path,newValue):
    path = translator[path]
    path_splitted = path.split("/")
    key = path_splitted[-1]
    path = path_splitted[:-1]
    
    for item in path:
        if item not in dictionary:
            dictionary[item] = {}
            dictionary = dictionary[item]
        else:
            dictionary = dictionary[item]

    dictionary[key] = newValue
