node {
    stage('build'){
        echo "building"
        sh "env | sort"
    }
}
stage('Deploy approval'){
    input "Deploy to prod?"
}
node {
    stage('deploy to prod'){
        echo "deploying"
    }
}
 
 
 
      
 
