pipeline {
    agent any
    environment {
        SERVICE_NAME    = 'iotgps-camera-integration'
        ECR_REPO        = 'iotgps-camera-integration'
        AWS_REGION      = 'ap-south-1'
        AWS_ACCOUNT_ID  = '359703527435'
        DOCKER_CONFIG   = "${WORKSPACE}/.docker"
        TCP_SERVER_HOST = '43.204.189.185'
        TCP_SERVER_USER = 'ubuntu'
        DEPLOY_PATH     = '/srv/iotgps-camera-integration'
    }
    triggers {
        githubPush()
        pollSCM('H/5 * * * *')
    }
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Fetch Env from S3') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'aws-ecr-credentials',
                    usernameVariable: 'AWS_ACCESS_KEY_ID',
                    passwordVariable: 'AWS_SECRET_ACCESS_KEY'
                )]) {
                    sh """
                        aws s3 cp s3://avls-env-files-359703527435-ap-south-1-an/${SERVICE_NAME}/.env .env
                    """
                }
            }
        }
        stage('Set Image Tag') {
            steps {
                script {
                    env.COMMIT_ID = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.IMAGE_TAG = env.COMMIT_ID
                    echo "Building ${env.SERVICE_NAME} with tag ${env.IMAGE_TAG}"
                }
            }
        }
        stage('AWS ECR Login') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'aws-ecr-credentials',
                    usernameVariable: 'AWS_ACCESS_KEY_ID',
                    passwordVariable: 'AWS_SECRET_ACCESS_KEY'
                )]) {
                    sh '''
                        mkdir -p "$DOCKER_CONFIG"
                        aws ecr get-login-password --region $AWS_REGION | \
                        docker login --username AWS --password-stdin \
                        ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
                    '''
                }
            }
        }
        stage('Build Docker Image') {
            steps {
                sh '''
                    docker build \
                      -t $ECR_REPO:$IMAGE_TAG \
                      -t $ECR_REPO:latest \
                      .
                '''
            }
        }
        stage('Push to ECR') {
            steps {
                sh '''
                    docker tag $ECR_REPO:$IMAGE_TAG ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/$ECR_REPO:$IMAGE_TAG
                    docker tag $ECR_REPO:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/$ECR_REPO:latest
                    docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/$ECR_REPO:$IMAGE_TAG
                    docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/$ECR_REPO:latest
                '''
            }
        }
        stage('Deploy to TCP Server') {
            steps {
                sshagent(['tcp-server-ssh-key']) {
                    sh """
                        scp -o StrictHostKeyChecking=yes docker-compose.yml ${TCP_SERVER_USER}@${TCP_SERVER_HOST}:/tmp/camera-compose-${BUILD_NUMBER}.yml
                        ssh -o StrictHostKeyChecking=yes ${TCP_SERVER_USER}@${TCP_SERVER_HOST} '
                            set -e
                            sudo mkdir -p ${DEPLOY_PATH}
                            sudo chown -R ubuntu:ubuntu ${DEPLOY_PATH}
                            backup_dir="/home/ubuntu/backups/camera-compose-${BUILD_NUMBER}-\$(date +%Y%m%d-%H%M%S)"
                            mkdir -p "\$backup_dir"
                            if [ -f ${DEPLOY_PATH}/docker-compose.yml ]; then
                                cp ${DEPLOY_PATH}/docker-compose.yml "\$backup_dir/docker-compose.yml"
                            fi
                            install -m 0644 /tmp/camera-compose-${BUILD_NUMBER}.yml ${DEPLOY_PATH}/docker-compose.yml
                            aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
                            docker pull ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}
                            cd ${DEPLOY_PATH}
                            IMAGE_TAG=${IMAGE_TAG} docker compose up -d --force-recreate
                            for attempt in \$(seq 1 30); do
                                status=\$(docker inspect --format="{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}" iotgps-camera-integration)
                                if [ "\$status" = "healthy" ] || [ "\$status" = "running" ]; then
                                    echo "Container is \$status on image ${IMAGE_TAG}"
                                    curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:5005/api/live-stream | grep -E "400|401"
                                    docker image prune -af --filter "until=24h" || true
                                    exit 0
                                fi
                                sleep 2
                            done
                            docker logs --tail 100 iotgps-camera-integration
                            exit 1
                        '
                    """
                }
            }
        }
    }
    post {
        success {
            emailext(
                to: 'sudhish.hajela@qtloads.com, sunnykumar@qtloads.com, devops@qtloads.com, brajesh.imcl@gmail.com, sachin.samadhiya@qtloads.com',
                mimeType: 'text/html',
                subject: "[Build-Release-Status] ${env.JOB_NAME} SUCCESS #${env.BUILD_NUMBER}",
                body: """
                <h2 style="color:green;">Deployment Successful</h2>
                <table border="1" cellpadding="5" cellspacing="0">
                    <tr><td><b>Service</b></td><td>${env.SERVICE_NAME}</td></tr>
                    <tr><td><b>Build</b></td><td>${env.BUILD_NUMBER}</td></tr>
                    <tr><td><b>Commit ID</b></td><td>${env.COMMIT_ID}</td></tr>
                    <tr><td><b>Image Tag</b></td><td>${env.IMAGE_TAG}</td></tr>
                    <tr><td><b>Server</b></td><td>${env.TCP_SERVER_HOST} (Port 5005)</td></tr>
                    <tr><td><b>Status</b></td><td>SUCCESS</td></tr>
                    <tr><td><b>Jenkins URL</b></td><td>${env.BUILD_URL}</td></tr>
                </table>
                """
            )
        }
        failure {
            emailext(
                to: 'sudhish.hajela@qtloads.com, sunnykumar@qtloads.com, devops@qtloads.com, brajesh.imcl@gmail.com, sachin.samadhiya@qtloads.com',
                mimeType: 'text/html',
                subject: "[Build-Release-Status] ${env.JOB_NAME} FAILURE #${env.BUILD_NUMBER}",
                body: """
                <h2 style="color:red;">Deployment Failed</h2>
                <table border="1" cellpadding="5" cellspacing="0">
                    <tr><td><b>Service</b></td><td>${env.SERVICE_NAME}</td></tr>
                    <tr><td><b>Build</b></td><td>${env.BUILD_NUMBER}</td></tr>
                    <tr><td><b>Commit ID</b></td><td>${env.COMMIT_ID}</td></tr>
                    <tr><td><b>Image Tag</b></td><td>${env.IMAGE_TAG}</td></tr>
                    <tr><td><b>Server</b></td><td>${env.TCP_SERVER_HOST}</td></tr>
                    <tr><td><b>Status</b></td><td>FAILURE</td></tr>
                    <tr><td><b>Jenkins URL</b></td><td>${env.BUILD_URL}</td></tr>
                </table>
                """
            )
        }
        always {
            sh 'docker rmi $ECR_REPO:$IMAGE_TAG $ECR_REPO:latest || true'
            cleanWs()
        }
    }
}
