from selenium.webdriver.common.by import By


class SiteLocators:
    # Login Page
    USERNAME_INPUT = (By.ID, 'email')
    PASSWORD_INPUT = (By.ID, 'password')
    SUBMIT_BUTTON = (By.XPATH, "//button[@type='submit']")

    # Make Wheel Page
    COMMON_ELEMENT = lambda x: f"//option[text()= '{x}']/parent::select"
    TYRE_SIZE_INPUT = (By.CSS_SELECTOR, "input[placeholder= 'Enter tyre size (e.g. 205/55 R16 91 H)']")
    MIN_AVAILABLE_QUANTITY_INPUT = (By.XPATH, "(//input[@placeholder= 'Min Availability'])[2]")
    SEARCH_BUTTON = (By.XPATH, "(//button[text()= 'Search'])[2]")
    SPINNER = (By.XPATH, "//div[contains(@class, 'animate-spin')]")
    FIRST_RESULT = (By.XPATH, "(//table)[2]/tbody/tr[1]")
    GENERATE_BY_AI_BUTTON = (By.XPATH, "//button[text()= 'Generate by AI']")
    TITLE_INPUT = (By.CSS_SELECTOR, "input[placeholder= 'Enter or edit title...']")
    DESCRIPTION_INPUT = (By.XPATH, "//label[text()= 'Description']/following-sibling::textarea")
    SAVE_BUTTON = (By.XPATH, "//button[text()= 'Submit']")
    NO_TYRE_FOUND_MESSAGE = (By.XPATH, "//div[text()= 'No tyres found']")
    SEARCH_BUTTON_2 = (By.XPATH, "(//button[text()= 'Search'])[1]")
    NO_RIM_FOUND_MESSAGE = (By.XPATH, "//div[text()= 'No rims found']")
    RIM_LOCATOR = lambda a, b, c, d, e, f: (By.XPATH, f"(//tr/td[text()= '{a}']/following-sibling::td[text()= '{b}']/following-sibling::td[text()= '{c}']/following-sibling::td[text()= '{d}']/following-sibling::td[text()= '{e} - {e}']/following-sibling::td[text()= '{f}'])[1]")
