pipeline {
    agent any
    environment {
        PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
    }
    
    stages {
    stage('Checkout') {
        steps {
            checkout scm
    }
}
    stage('DEBUG - environment') {
            steps {
                sh '''
                    echo "=== WHO AM I ==="
                    whoami

                    echo "=== PATH ==="
                    echo $PATH

                    echo "=== DOCKER INFO ==="
                    which docker || true
                    docker --version || true

                    echo "=== DOCKER ENV ==="
                    env | grep -i docker || true

                    echo "=== DOCKER CONTEXT ==="
                    docker context ls || true
                    docker context show || true

                    echo "=== SOCKET CHECK ==="
                    ls -la /var/run/docker.sock || true
                    ls -la $HOME/.colima/default/docker.sock || true

                    echo "=== DOCKER HOST ==="
                    echo $DOCKER_HOST

                    echo "=== TEST CONNECTION ==="
                    docker ps || true
                '''
            }
        }

    stage('Build') {
        steps {
            sh 'docker build -t myapp .'
    }
}

    stage('Push') {
        steps {
            sh 'docker push myrepo/myapp:latest'
    }
}

    stage('Deploy') {
        steps {
            sh 'pulumi up --yes'
    }
}
}
}
