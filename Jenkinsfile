pipeline {
    agent any

    stage('Checkout') {
        steps {
            checkout scm
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
