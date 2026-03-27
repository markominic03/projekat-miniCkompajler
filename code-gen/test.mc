int zbirDo(int n){
    int rezultat;
    rezultat = 0;
    if(n > 0){
        rezultat = n + 1;
    }
    return rezultat;
}

int veci(int a){
    int b;
    b = 10;
    if(a > b){
        return a;
    }
    else{
        return b;
    }
}

int main(){
    int x;
    int y;
    int z;
    x = 5;
    y = zbirDo(x);
    z = veci(y);
    return z;
}