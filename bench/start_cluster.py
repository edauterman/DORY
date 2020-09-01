import sys, string, json, time
import subprocess
import benchClient

regionAMIs = {
        "us-east-1": "ami-057e79f5781fe8619",
        "us-east-2": "ami-09d625653d2d6cc74",
        }

filename = "../system.config"

f_config = open(filename, "r")
sysConfig = json.load(f_config)
f_config.close()

# US-EAST-1

cmd = "export AWS_DEFAULT_REGION=us-east-1"
process = subprocess.Popen(cmd, shell=True)
process.wait()

cmd = ('export AWS_DEFAULT_REGION=us-east-1; aws ec2 run-instances --image-id %s --count 2 --instance-type c5.large --key-name DoryKeyPair --placement "{\\\"AvailabilityZone\\\": \\\"us-east-1b\\\"}" --security-groups DoryGroup') % (regionAMIs["us-east-1"])
process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
out = process.stdout.read()
east12Config = json.loads(out)
east12IDs = [instance["InstanceId"] for instance in east12Config["Instances"]]

cmd = ('export AWS_DEFAULT_REGION=us-east-1; aws ec2 run-instances --image-id %s --count 5 --instance-type r5n.4xlarge --key-name DoryKeyPair --placement "{\\\"AvailabilityZone\\\": \\\"us-east-1b\\\"}" --security-groups DoryGroup') % (regionAMIs["us-east-1"])
#cmd = ('aws ec2 run-instances --image-id %s --count 5 --instance-type r5n.4xlarge --key-name DoryKeyPair --placement "{\\\"AvailabilityZone\\\": \\\"us-east-1b\\\"}" --security-groups DoryGroup') % (regionAMIs["us-east-1"])
process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
out = process.stdout.read()
east11Config = json.loads(out)
east11IDs = [instance["InstanceId"] for instance in east11Config["Instances"]]

time.sleep(10)

# first is master, next are servers 1, 3, 5, 7
server1Addrs = []
for i in range(len(east11IDs)):
    cmd = ('export AWS_DEFAULT_REGION=us-east-1; aws ec2 describe-instances --instance-ids "%s"') % (east11IDs[i])
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = process.stdout.read()
    c = json.loads(out)
    server1Addrs.append(c["Reservations"][0]["Instances"][0]["PublicIpAddress"])

# dory client, baseline client
clientAddrs = []
for i in range(len(east12IDs)):
    cmd = ('export AWS_DEFAULT_REGION=us-east-1; aws ec2 describe-instances --instance-ids "%s"') % (east12IDs[i])
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = process.stdout.read()
    c = json.loads(out)
    clientAddrs.append(c["Reservations"][0]["Instances"][0]["PublicIpAddress"])

print("Created all us-east-1 instances")
# US-EAST-2

cmd = "export AWS_DEFAULT_REGION=us-east-2"
process = subprocess.Popen(cmd, shell=True)
process.wait()

cmd = ('export AWS_DEFAULT_REGION=us-east-2; aws ec2 run-instances --image-id %s --count 5 --instance-type r5n.4xlarge --key-name DoryKeyPair --placement "{\\\"AvailabilityZone\\\": \\\"us-east-2b\\\"}" --security-groups DoryGroup') % (regionAMIs["us-east-2"]) 
process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
out = process.stdout.read()
east2Config = json.loads(out)
east2IDs = [instance["InstanceId"] for instance in east2Config["Instances"]]

time.sleep(10)

# servers 2, 4, 6, 8, baseline
server2Addrs = []
for i in range(len(east2IDs)):
    cmd = ('export AWS_DEFAULT_REGION=us-east-2; aws ec2 describe-instances --instance-ids "%s"') % (east2IDs[i])
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = process.stdout.read()
    c = json.loads(out)
    server2Addrs.append(c["Reservations"][0]["Instances"][0]["PublicIpAddress"])

print("Created all us-east-2 instances")

sysConfig["MasterAddr"] = server1Addrs[0]
sysConfig["MasterID"] = east11IDs[0]
sysConfig["ClientAddrs"] = [clientAddrs[0]]
sysConfig["ClientIDs"] = [east12IDs[0]]
for i in range(len(sysConfig["Servers"])):
    if i % 2 == 0:
        sysConfig["Servers"][i]["Addr"] = server1Addrs[int(i/2 + 1)]
        sysConfig["Servers"][i]["ID"] = east11IDs[int(i/2 + 1)]
    else:
        sysConfig["Servers"][i]["Addr"] = server2Addrs[int(i/2 + 1)]
        sysConfig["Servers"][i]["ID"] = east2IDs[int(i/2 + 1)]

sysConfig["BaselineServerAddr"] = server2Addrs[0]
sysConfig["BaselineServerID"] = east2IDs[0]
sysConfig["BaselineClientAddr"] = [clientAddrs[1]]
sysConfig["BaselineClientID"] = east12IDs[1]

sysConfig["SSHKeyPath"] = "~/.ssh/dory.pem"

sysConfigBlob = json.dumps(sysConfig)

f_config = open(filename, "w")
f_config.write(sysConfigBlob)
    
f_config.close()

sshKeyPath = sysConfig["SSHKeyPath"]

replicaPorts = [server["Port"] for server in sysConfig["Servers"]]
replicas = [server["Addr"] for server in sysConfig["Servers"]]

masterConfig = {
        "MasterAddr": sysConfig["MasterAddr"],
        "MasterPort": sysConfig["MasterPort"],
        "Addr": replicas,
        "Port": replicaPorts,
        "CertFile": sysConfig["MasterCertFile"],
        "KeyFile": sysConfig["MasterKeyFile"],
        "OutDir": sysConfig["OutDir"]
    }
masterConfigBlob = json.dumps(masterConfig)

print("Copying config files to instances")

with open("../src/config/master.config", "w") as f:
    f.write(masterConfigBlob)

if sysConfig["MasterAddr"] != "127.0.0.1":
    cmd = ("scp -i %s -o StrictHostKeyChecking=no $(PWD)/../src/config/master.config ec2-user@%s:~/dory/src/config/master.config") % (sshKeyPath, sysConfig["MasterAddr"])
    process = subprocess.Popen(cmd, shell=True)
    process.wait()

for i in range(len(sysConfig["Servers"])):
    serverConfig = {
            "Addr": sysConfig["Servers"][i]["Addr"],
            "Port": sysConfig["Servers"][i]["Port"],
            "CertFile": sysConfig["Servers"][i]["CertFile"],
            "KeyFile": sysConfig["Servers"][i]["KeyFile"],
            "OutDir": sysConfig["OutDir"],
            "ClientMaskKey": sysConfig["ClientMaskKey"],
            "ClientMacKey": sysConfig["ClientMacKey"]
        }
    serverNum = i + 1
    serverConfigBlob = json.dumps(serverConfig)

    with open(("../src/config/server%d.config") % (serverNum), "w") as f:
        f.write(serverConfigBlob)

    if sysConfig["Servers"][i]["Addr"] != "127.0.0.1":
        cmd = ("scp -i %s -o StrictHostKeyChecking=no $(PWD)/../src/config/server%d.config ec2-user@%s:~/dory/src/config/server%d.config") % (sshKeyPath, serverNum, sysConfig["Servers"][i]["Addr"], serverNum)
        process = subprocess.Popen(cmd, shell=True)
        process.wait()

clientConfig = {
        "MasterAddr": sysConfig["MasterAddr"],
        "MasterPort": sysConfig["MasterPort"],
        "Addr": replicas,
        "Port": replicaPorts,
        "MaskKey": sysConfig["ClientMaskKey"],
        "MacKey": sysConfig["ClientMacKey"]
    }
clientConfigBlob = json.dumps(clientConfig)

with open("../src/config/client.config", "w") as f:
    f.write(clientConfigBlob)

for i in range(len(sysConfig["ClientAddrs"])):

    if sysConfig["ClientAddrs"][i] != "127.0.0.1":
        cmd = ("scp -i %s -o StrictHostKeyChecking=no $(PWD)/../src/config/client.config ec2-user@%s:~/dory/src/config/client.config") % (sshKeyPath, sysConfig["ClientAddrs"][i])
        process = subprocess.Popen(cmd, shell=True)
        process.wait()

print("Cluster setup done.")