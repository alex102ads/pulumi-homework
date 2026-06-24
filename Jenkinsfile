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

    stage('Build') {
        steps {
            sh 'docker build -t myapp ./app/'
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
