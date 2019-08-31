from fabric2 import Connection
from fabric2 import task
from fabric2 import config
import os
from xml.etree import ElementTree as ET
import uuid
import glob

workflow_components = ['input.xml', 'binding.xml', 'flow.xml', 'result.xml', 'tool.xml']

@task
def update_workflow_xml(c, workflow_name, tool_name, workflow_version, production_str=""):
    production = production_str=="production"

    local_temp_path = os.path.join("/tmp/{}_{}_{}".format(workflow_name, workflow_version, str(uuid.uuid4())))
    c.local("mkdir -p {}".format(local_temp_path))

    for component in workflow_components:
        rewrite_workflow_component(component, workflow_name, tool_name, workflow_version, local_temp_path)

    if production:
        c.sudo("mkdir -p /ccms/workflows/{}/versions".format(workflow_name), user=c["env"]["production_user"], pty=True)
        c.sudo("mkdir -p /ccms/workflows/{}/versions/{}".format(workflow_name, workflow_version), user=c["env"]["production_user"], pty=True)
    else:
        c.run("mkdir -p /ccms/workflows/{}/versions".format(workflow_name))
        c.run("mkdir -p /ccms/workflows/{}/versions/{}".format(workflow_name, workflow_version))

    for component in workflow_components:
        update_workflow_component(c, local_temp_path, component, workflow_version=workflow_version, production=production) #Explicitly adding versioned
        update_workflow_component(c, local_temp_path, component, production=production) #Adding to active default version

#Uploading the actual tools to the server
@task
def update_tools(c, workflow_name, workflow_version, production_str=""):
    production = production_str=="production"

    if production:
        c.sudo("mkdir -p /data/cluster/tools/{}/{}".format(workflow_name, workflow_version), user=c["env"]["production_user"])
    else:
        c.run("mkdir -p /data/cluster/tools/{}/{}".format(workflow_name, workflow_version))

    local_path = 'tools/{}/'.format(workflow_name)
    final_path = '/data/cluster/tools/{}/{}/'.format(workflow_name, workflow_version)

    update_folder(c, local_path, final_path, production=production)



#Utility Functions

def rewrite_workflow_component(component, workflow_name, tool_name, workflow_version, local_temp_path):
    local = os.path.join(workflow_name,component)
    temp = os.path.join(local_temp_path,component)
    tree = ET.parse(local)
    root = tree.getroot()
    if component in ['input.xml','result.xml']:
        root.set('id', workflow_name)
        root.set('version', workflow_version)
    elif component in ['flow.xml']:
        root.set('name', workflow_name)
    elif component in ['tool.xml']:
        for path in root.findall('pathSet'):
            if path.attrib['base'] == '$base':
                path.attrib['base'] = os.path.join(tool_name,workflow_version)
    tree.write(temp)

#TODO: Validate that the xml is also a valid workflow
def update_workflow_component(c, workflow_filename, component, workflow_version=None, production=False):
    local = os.path.join(workflow_filename,component)
    if workflow_version:
        server = '/ccms/workflows/{}/versions/{}/{}'.format(workflow_filename, workflow_version, component)
    else:
        server = '/ccms/workflows/{}/{}'.format(workflow_filename, component)
    update_file(c, local, server, production=production)



#Update File
def update_file(c, local_path, final_path, production=False):
    if production:
        remote_temp_path = os.path.join("/tmp/{}_{}".format(local_path.replace("/", "_"), str(uuid.uuid4())))
        c.put(local_path, remote_temp_path, preserve_mode=True)
        c.sudo('cp {} {}'.format(remote_temp_path, final_path), user=c["env"]["production_user"], pty=True)
    else:
        c.put(local_path, final_path, preserve_mode=True)

#TODO: update this to work with rsync
def update_folder(c, local_path, final_path, production=False):
    #Tar up local folder and upload to temporary space on server and untar
    local_temp_path = os.path.join("/tmp/{}_{}.tar".format(local_path.replace("/", "_"), str(uuid.uuid4())))
    cmd = "tar -C {} -chvf {} .".format(local_path, local_temp_path)
    print(cmd)
    os.system(cmd)

    remote_temp_tar_path = os.path.join("/tmp/{}_{}.tar".format(local_path.replace("/", "_"), str(uuid.uuid4())))
    c.put(local_temp_path, remote_temp_tar_path, preserve_mode=True)

    remote_temp_path = os.path.join("/tmp/{}_{}".format(local_path.replace("/", "_"), str(uuid.uuid4())))
    c.run("mkdir {}".format(remote_temp_path))
    c.run("tar -C {} -xvf {}".format(remote_temp_path, remote_temp_tar_path))

    if production:
        c.sudo('rsync -rlptDv {}/ {}'.format(remote_temp_path, final_path), user=c["env"]["production_user"], pty=True)
    else:
        c.run('rsync -rlptDv {}/ {}'.format(remote_temp_path, final_path))
