# depend to export SONAR_TOKEN=your token before running this script (must be executed before running this script)
# -X is for debug mode, it will print more information about the execution of the sonar-scanner command.
sonar-scanner -Dsonar.token="$SONAR_TOKEN" -X