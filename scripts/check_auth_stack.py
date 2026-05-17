from passlib.context import CryptContext


def main() -> None:
    ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password = "testpass123"
    print(f"password length={len(password)}")
    hashed = ctx.hash(password)
    print("hash ok")
    print(ctx.verify(password, hashed))


if __name__ == "__main__":
    main()
