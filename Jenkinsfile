pipeline {
    agent any
    
    stages {
    stage('Checkout') {
        steps {
            checkout scm
    }
}
    stage('CheckDocker') {
        steps {
            sh 'docker --version'
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
